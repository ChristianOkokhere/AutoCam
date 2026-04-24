"""Pipeline executor — runs an EditStack against an image."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image

from autocam.io.image import load_image
from autocam.ops import Op, PipelineCtx
from autocam.pipeline.color import linear_to_srgb, srgb_to_linear
from autocam.pipeline.stack import EditStack

Float32Array = npt.NDArray[np.float32]

PREVIEW_MAX_EDGE = 2048


def _resize_to_max(img: Float32Array, max_edge: int) -> Float32Array:
    """Lanczos downscale in display gamma so edges stay clean."""
    height, width = img.shape[:2]
    longest = max(height, width)
    if longest <= max_edge:
        return img
    scale = max_edge / longest
    new_w = max(1, round(width * scale))
    new_h = max(1, round(height * scale))
    display = linear_to_srgb(img)
    arr8 = np.ascontiguousarray(np.clip(display * 255.0, 0, 255).astype(np.uint8))
    pil = Image.fromarray(arr8).resize((new_w, new_h), Image.LANCZOS)
    back = np.asarray(pil, dtype=np.float32) / 255.0
    return srgb_to_linear(back)


def run_stack(
    stack: EditStack,
    source: Path | str | None = None,
    *,
    preview: bool = False,
) -> Float32Array:
    """Execute a stack and return the final linear-sRGB float32 image."""
    source_path = Path(source) if source is not None else Path(stack.source)
    img = load_image(source_path)
    if preview:
        img = _resize_to_max(img, PREVIEW_MAX_EDGE)

    ctx = PipelineCtx(source_path=str(source_path), preview=preview)
    for op in stack.ops:
        img = op.apply(img, ctx)
    return img


class Pipeline:
    """Imperative builder over an :class:`EditStack`."""

    def __init__(self, source: Path | str) -> None:
        self.stack = EditStack(source=str(source))

    def add(self, op: Op) -> Pipeline:
        self.stack.append(op)
        return self

    def run(self, *, preview: bool = False) -> Float32Array:
        return run_stack(self.stack, preview=preview)
