"""Detail ops: sharpen (unsharp mask via Pillow)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from PIL import Image, ImageFilter

from autocam.ops.base import Float32Array, Op, PipelineCtx, register
from autocam.pipeline.color import linear_to_srgb, srgb_to_linear


@register
@dataclass
class SharpenOp(Op):
    """Unsharp mask.

    ``amount`` is the Pillow ``percent`` (0-200 typical).
    ``radius`` is the blur radius in pixels.
    ``threshold`` is the minimum pixel difference (0-255) to sharpen.
    """

    name: ClassVar[str] = "detail.sharpen"
    amount: float = 50.0
    radius: float = 1.0
    threshold: float = 0.0

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        display = linear_to_srgb(img)
        arr8 = np.ascontiguousarray(np.clip(display * 255.0, 0, 255).astype(np.uint8))
        pil = Image.fromarray(arr8)
        out = pil.filter(
            ImageFilter.UnsharpMask(
                radius=float(self.radius),
                percent=int(self.amount),
                threshold=int(self.threshold),
            )
        )
        back = np.asarray(out, dtype=np.float32) / 255.0
        return srgb_to_linear(back)
