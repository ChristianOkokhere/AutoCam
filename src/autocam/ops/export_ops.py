"""Export op — writes the current pipeline buffer to disk as 8-bit sRGB."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

import numpy as np
from PIL import Image

from autocam.ops.base import Float32Array, Op, PipelineCtx, register
from autocam.pipeline.color import linear_to_srgb

Format = Literal["jpeg", "png", "tiff"]


@register
@dataclass
class ExportSaveOp(Op):
    """Save the current buffer; returns it unchanged so the stack can continue."""

    name: ClassVar[str] = "export.save"
    path: str = ""
    format: Format = "jpeg"
    quality: int = 90

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        if not self.path:
            raise ValueError("export.save requires a non-empty `path`")
        display = linear_to_srgb(img)
        arr8 = np.ascontiguousarray(np.clip(display * 255.0, 0, 255).astype(np.uint8))
        pil = Image.fromarray(arr8)
        kwargs: dict = {"format": self.format.upper()}
        if self.format == "jpeg":
            kwargs["quality"] = int(self.quality)
        pil.save(self.path, **kwargs)
        return img
