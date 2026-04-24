"""Geometric ops: crop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from autocam.ops.base import Float32Array, Op, PipelineCtx, register


@register
@dataclass
class CropOp(Op):
    """Crop to a normalized rectangle in ``[0, 1]`` of the input size."""

    name: ClassVar[str] = "geom.crop"
    x: float = 0.0
    y: float = 0.0
    w: float = 1.0
    h: float = 1.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        height, width = img.shape[:2]
        x0 = round(self.x * width)
        y0 = round(self.y * height)
        x1 = round((self.x + self.w) * width)
        y1 = round((self.y + self.h) * height)
        x0 = max(0, min(width - 1, x0))
        y0 = max(0, min(height - 1, y0))
        x1 = max(x0 + 1, min(width, x1))
        y1 = max(y0 + 1, min(height, y1))
        return np.ascontiguousarray(img[y0:y1, x0:x1])
