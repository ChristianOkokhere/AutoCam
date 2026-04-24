"""Tonal ops: exposure, contrast, highlights, shadows, whites, blacks.

Exposure is a pure multiplication in linear space (the only physically
accurate place for it). The rest operate in display-gamma sRGB so shifts
feel perceptually even, then convert back to linear.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from autocam.ops.base import Float32Array, Op, PipelineCtx, register
from autocam.pipeline.color import linear_to_srgb, srgb_to_linear


def _weighted_shift(img: Float32Array, weight: Float32Array, shift: float) -> Float32Array:
    """Add ``shift * weight`` in display gamma, round-trip back to linear."""
    display = linear_to_srgb(img)
    result = np.clip(display + shift * weight, 0.0, 1.0)
    return srgb_to_linear(result)


@register
@dataclass
class ExposureOp(Op):
    """Multiply linear values by ``2 ** ev`` (photographic exposure)."""

    name: ClassVar[str] = "tone.exposure"
    ev: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        return (img * (2.0**self.ev)).astype(np.float32)


@register
@dataclass
class ContrastOp(Op):
    """S-curve contrast pivoting at mid-gray. ``amount`` in ``-100..+100``."""

    name: ClassVar[str] = "tone.contrast"
    amount: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        display = linear_to_srgb(img)
        k = self.amount / 100.0
        y = display + k * display * (1.0 - display) * (2.0 * display - 1.0)
        return srgb_to_linear(np.clip(y, 0.0, 1.0))


@register
@dataclass
class HighlightsOp(Op):
    """Pull down (negative) or push up (positive) the upper tonal range."""

    name: ClassVar[str] = "tone.highlights"
    amount: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        display = linear_to_srgb(img)
        t = np.clip((display - 0.5) / 0.5, 0.0, 1.0)
        weight = (t * t).astype(np.float32)
        return _weighted_shift(img, weight, self.amount / 100.0 * 0.3)


@register
@dataclass
class ShadowsOp(Op):
    """Lift (positive) or crush (negative) the lower tonal range."""

    name: ClassVar[str] = "tone.shadows"
    amount: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        display = linear_to_srgb(img)
        t = np.clip((0.5 - display) / 0.5, 0.0, 1.0)
        weight = (t * t).astype(np.float32)
        return _weighted_shift(img, weight, self.amount / 100.0 * 0.3)


@register
@dataclass
class WhitesOp(Op):
    """Push the white-point region. ``amount`` in ``-100..+100``."""

    name: ClassVar[str] = "tone.whites"
    amount: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        display = linear_to_srgb(img)
        weight = np.clip((display - 0.75) / 0.25, 0.0, 1.0).astype(np.float32)
        return _weighted_shift(img, weight, self.amount / 100.0 * 0.2)


@register
@dataclass
class BlacksOp(Op):
    """Push the black-point region. ``amount`` in ``-100..+100``."""

    name: ClassVar[str] = "tone.blacks"
    amount: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        display = linear_to_srgb(img)
        weight = np.clip((0.25 - display) / 0.25, 0.0, 1.0).astype(np.float32)
        return _weighted_shift(img, weight, self.amount / 100.0 * 0.2)
