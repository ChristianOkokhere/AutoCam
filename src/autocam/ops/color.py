"""Color ops: white balance, saturation, vibrance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from autocam.ops.base import Float32Array, Op, PipelineCtx, register
from autocam.pipeline.color import luminance


@register
@dataclass
class WhiteBalanceOp(Op):
    """Kelvin-ish temp shift + green/magenta tint via channel multipliers.

    ``temp_shift`` in ``-100..+100``: negative cools, positive warms.
    ``tint`` in ``-100..+100``: negative adds green, positive adds magenta.
    """

    name: ClassVar[str] = "color.white_balance"
    temp_shift: float = 0.0
    tint: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        t = self.temp_shift / 500.0
        m = self.tint / 500.0
        mult = np.array([1.0 + t, 1.0 - m, 1.0 - t], dtype=np.float32)
        return (img * mult).astype(np.float32)


@register
@dataclass
class SaturationOp(Op):
    """Luminance-preserving linear saturation. ``amount`` in ``-100..+100``."""

    name: ClassVar[str] = "color.saturation"
    amount: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        factor = 1.0 + self.amount / 100.0
        lum = luminance(img)
        return (lum + (img - lum) * factor).astype(np.float32)


@register
@dataclass
class VibranceOp(Op):
    """Saturation that eases off on already-saturated pixels."""

    name: ClassVar[str] = "color.vibrance"
    amount: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        factor = 1.0 + self.amount / 100.0
        lum = luminance(img)
        max_c = img.max(axis=-1, keepdims=True)
        min_c = img.min(axis=-1, keepdims=True)
        current_sat = (max_c - min_c) / (np.maximum(max_c, 1e-6))
        weight = 1.0 - current_sat
        effective = 1.0 + (factor - 1.0) * weight
        return (lum + (img - lum) * effective).astype(np.float32)
