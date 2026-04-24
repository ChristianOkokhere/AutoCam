"""Color-space conversions used across the pipeline.

The pipeline keeps pixels in linear-sRGB float32 so photographic operations
(exposure, white balance, saturation) behave correctly. Ops that reason about
perceptual tonality convert to display-gamma sRGB locally, operate there, and
convert back.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

Float32Array = npt.NDArray[np.float32]


def srgb_to_linear(img: Float32Array) -> Float32Array:
    """Convert sRGB (display-gamma, 0-1 range) to linear sRGB."""
    threshold = 0.04045
    out = np.where(
        img <= threshold,
        img / 12.92,
        ((np.maximum(img, 0.0) + 0.055) / 1.055) ** 2.4,
    )
    return out.astype(np.float32)


def linear_to_srgb(img: Float32Array) -> Float32Array:
    """Convert linear sRGB to sRGB (display-gamma, 0-1 range)."""
    threshold = 0.0031308
    out = np.where(
        img <= threshold,
        img * 12.92,
        1.055 * np.power(np.maximum(img, 0.0), 1.0 / 2.4) - 0.055,
    )
    return out.astype(np.float32)


# Rec. 709 / sRGB luminance weights.
LUMA_WEIGHTS = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def luminance(img: Float32Array) -> Float32Array:
    """Compute per-pixel luminance (keeps the last axis for broadcasting)."""
    return (img * LUMA_WEIGHTS).sum(axis=-1, keepdims=True).astype(np.float32)
