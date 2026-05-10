"""Mask ops — produce a single-channel ``[0, 1]`` mask in ``ctx.masks``.

These are deterministic, dependency-free masks. AI-driven masks (FastSAM,
rembg, MediaPipe) ride in on a follow-up phase that adds the heavyweight
optional deps; the architecture here is the same — a mask op populates
``ctx.masks[self.id]`` and any later op can scope its effect through it
by setting ``mask=<that id>``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

import numpy as np
from PIL import Image, ImageFilter

from autocam.ops.base import Float32Array, MaskArray, MaskOp, PipelineCtx, register
from autocam.pipeline.color import linear_to_srgb, luminance

LumRange = Literal["shadows", "mids", "highs"]


def _feather(mask: MaskArray, feather: float) -> MaskArray:
    """Gaussian-blur a mask. ``feather`` is a fraction of the short edge."""
    if feather <= 0.0:
        return mask
    h, w = mask.shape
    radius = max(1.0, float(feather) * min(h, w))
    arr8 = np.clip(mask * 255.0, 0, 255).astype(np.uint8)
    pil = Image.fromarray(arr8, mode="L").filter(ImageFilter.GaussianBlur(radius))
    return (np.asarray(pil, dtype=np.float32) / 255.0).astype(np.float32)


@register
@dataclass
class LuminosityMaskOp(MaskOp):
    """Mask weighted by where each pixel sits on the tonal scale.

    ``range`` selects shadows / mids / highs. ``feather`` is the Gaussian
    blur radius as a fraction of the short edge (0 = hard mask).
    """

    name: ClassVar[str] = "mask.luminosity"
    range: LumRange = "highs"
    feather: float = 0.05

    def compute_mask(self, img: Float32Array, ctx: PipelineCtx) -> MaskArray:
        # Read luminance in display gamma so "shadows" / "highs" feel right.
        display = linear_to_srgb(img)
        lum = luminance(display)[..., 0]  # (H, W)

        if self.range == "shadows":
            t = np.clip((0.5 - lum) / 0.5, 0.0, 1.0)
            mask = (t * t).astype(np.float32)
        elif self.range == "highs":
            t = np.clip((lum - 0.5) / 0.5, 0.0, 1.0)
            mask = (t * t).astype(np.float32)
        else:  # mids
            mask = (1.0 - 2.0 * np.abs(lum - 0.5)).clip(0.0, 1.0).astype(np.float32)

        return _feather(mask, self.feather)


@register
@dataclass
class ColorRangeMaskOp(MaskOp):
    """Mask pixels near a hue cluster, gated by saturation and luminance.

    ``hue_deg`` is the centre hue in degrees (0..360). ``hue_width_deg`` is the half-width
    at which the falloff reaches ~0. ``sat_min`` / ``lum_min`` / ``lum_max``
    are display-gamma gates. ``feather`` softens edges.
    """

    name: ClassVar[str] = "mask.color_range"
    hue_deg: float = 30.0
    hue_width_deg: float = 30.0
    sat_min: float = 0.10
    lum_min: float = 0.05
    lum_max: float = 0.95
    feather: float = 0.02

    def compute_mask(self, img: Float32Array, ctx: PipelineCtx) -> MaskArray:
        display = linear_to_srgb(img)
        h_deg, s, lum = _rgb_to_hsl_arrays(display)

        # Wrap-aware hue distance, in degrees, to the cluster centre.
        d = np.abs(((h_deg - self.hue_deg + 180.0) % 360.0) - 180.0)
        width = max(1e-3, float(self.hue_width_deg))
        hue_w = np.clip(1.0 - d / width, 0.0, 1.0)
        hue_w = (hue_w * hue_w).astype(np.float32)

        sat_w = np.clip((s - self.sat_min) / max(1e-3, 1.0 - self.sat_min), 0.0, 1.0)
        lum_w = np.where(
            (lum >= self.lum_min) & (lum <= self.lum_max),
            1.0,
            0.0,
        ).astype(np.float32)

        mask = (hue_w * sat_w * lum_w).astype(np.float32)
        return _feather(mask, self.feather)


@register
@dataclass
class InvertMaskOp(MaskOp):
    """Produce a mask that's ``1 - target`` of an earlier mask op."""

    name: ClassVar[str] = "mask.invert"
    target: str = ""

    def compute_mask(self, img: Float32Array, ctx: PipelineCtx) -> MaskArray:
        if not self.target:
            raise ValueError("mask.invert requires a `target` op id")
        try:
            base = ctx.masks[self.target]
        except KeyError as exc:
            raise KeyError(f"mask.invert: target {self.target!r} hasn't been computed yet") from exc
        return (1.0 - base).clip(0.0, 1.0).astype(np.float32)


def _rgb_to_hsl_arrays(rgb: Float32Array) -> tuple[Float32Array, Float32Array, Float32Array]:
    """Vectorised RGB → HSL on a display-gamma ``(H, W, 3)`` array.

    Returns hue in degrees ``[0, 360)``, saturation ``[0, 1]``, luminance ``[0, 1]``.
    """
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin
    lum = (cmax + cmin) * 0.5

    eps = 1e-6
    sat = np.where(
        delta < eps,
        0.0,
        delta / np.maximum(eps, 1.0 - np.abs(2.0 * lum - 1.0)),
    )

    hue = np.zeros_like(cmax)
    safe_delta = np.where(delta < eps, 1.0, delta)
    h_r = ((g - b) / safe_delta) % 6.0
    h_g = ((b - r) / safe_delta) + 2.0
    h_b = ((r - g) / safe_delta) + 4.0
    hue = np.where(cmax == r, h_r, hue)
    hue = np.where(cmax == g, h_g, hue)
    hue = np.where(cmax == b, h_b, hue)
    hue = np.where(delta < eps, 0.0, hue)
    hue_deg = (hue * 60.0) % 360.0
    return hue_deg.astype(np.float32), sat.astype(np.float32), lum.astype(np.float32)
