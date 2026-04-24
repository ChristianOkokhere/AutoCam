"""Parametric RGB / per-channel tone curve."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Literal

import numpy as np

from autocam.ops.base import Float32Array, Op, PipelineCtx, register
from autocam.pipeline.color import linear_to_srgb, srgb_to_linear

Channel = Literal["rgb", "r", "g", "b"]


def _identity_points() -> list[list[float]]:
    return [[0.0, 0.0], [1.0, 1.0]]


@register
@dataclass
class RgbCurveOp(Op):
    """Piecewise-linear curve in display-gamma sRGB.

    ``points`` is a list of ``[input, output]`` pairs in ``[0, 1]``.
    ``channel`` applies the curve to all RGB channels or one of R/G/B.
    """

    name: ClassVar[str] = "curve.rgb"
    points: list[list[float]] = field(default_factory=_identity_points)
    channel: Channel = "rgb"

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        pts = sorted(self.points, key=lambda p: p[0])
        xs = np.array([p[0] for p in pts], dtype=np.float32)
        ys = np.array([p[1] for p in pts], dtype=np.float32)

        display = linear_to_srgb(img)
        if self.channel == "rgb":
            out = np.interp(display, xs, ys).astype(np.float32)
        else:
            idx = {"r": 0, "g": 1, "b": 2}[self.channel]
            out = display.copy()
            out[..., idx] = np.interp(display[..., idx], xs, ys).astype(np.float32)
        return srgb_to_linear(np.clip(out, 0.0, 1.0))
