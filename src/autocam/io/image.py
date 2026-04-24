"""Image file I/O — JPEG/PNG/TIFF via Pillow.

Conversion rule: everything on disk is display-gamma sRGB 8-bit; everything
inside the pipeline is linear-sRGB float32. These two functions are the only
places where the conversion happens.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image

from autocam.pipeline.color import linear_to_srgb, srgb_to_linear

Float32Array = npt.NDArray[np.float32]


def load_image(path: Path | str) -> Float32Array:
    """Load a raster image and return ``(H, W, 3)`` linear-sRGB float32."""
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        arr = np.asarray(rgb, dtype=np.float32) / 255.0
    return srgb_to_linear(arr)


def save_image(
    img: Float32Array,
    path: Path | str,
    *,
    format: str = "jpeg",
    quality: int = 90,
) -> None:
    """Save a linear-sRGB float32 image as 8-bit display sRGB."""
    display = linear_to_srgb(img)
    arr8 = np.ascontiguousarray(np.clip(display * 255.0, 0, 255).astype(np.uint8))
    pil = Image.fromarray(arr8)
    kwargs: dict = {"format": format.upper()}
    if format.lower() == "jpeg":
        kwargs["quality"] = int(quality)
    pil.save(path, **kwargs)
