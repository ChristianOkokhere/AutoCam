"""Image I/O helpers.

The pipeline only ever calls :func:`load_any` — it dispatches to a raster
loader (Pillow) or a RAW loader (rawpy) based on the file extension and
returns the same linear-sRGB float32 shape either way.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt

from autocam.io.image import load_image, save_image
from autocam.io.raw import RAW_EXTENSIONS, is_raw_path, load_raw

Float32Array = npt.NDArray[np.float32]


def load_any(path: Path | str, *, preview: bool = False) -> Float32Array:
    """Load any supported image and return ``(H, W, 3)`` linear-sRGB float32."""
    if is_raw_path(path):
        return load_raw(path, preview=preview)
    return load_image(path)


__all__ = [
    "RAW_EXTENSIONS",
    "is_raw_path",
    "load_any",
    "load_image",
    "load_raw",
    "save_image",
]
