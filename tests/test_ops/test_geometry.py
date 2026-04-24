"""Tests for geometry ops."""

from __future__ import annotations

import numpy as np

from autocam.ops import PipelineCtx
from autocam.ops.geometry import CropOp

CTX = PipelineCtx(source_path="")


def test_crop_whole_image_is_identity(gradient_linear: np.ndarray) -> None:
    out = CropOp(x=0.0, y=0.0, w=1.0, h=1.0).apply(gradient_linear, CTX)
    assert out.shape == gradient_linear.shape
    assert np.allclose(out, gradient_linear)


def test_crop_center_halves_size(gradient_linear: np.ndarray) -> None:
    out = CropOp(x=0.25, y=0.25, w=0.5, h=0.5).apply(gradient_linear, CTX)
    h, w = gradient_linear.shape[:2]
    assert out.shape == (h // 2, w // 2, 3)


def test_crop_preserves_dtype(gradient_linear: np.ndarray) -> None:
    out = CropOp(x=0.1, y=0.1, w=0.5, h=0.5).apply(gradient_linear, CTX)
    assert out.dtype == np.float32
