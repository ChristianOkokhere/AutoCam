"""Tests for detail ops (sharpen)."""

from __future__ import annotations

import numpy as np

from autocam.ops import PipelineCtx
from autocam.ops.detail import SharpenOp

CTX = PipelineCtx(source_path="")


def test_sharpen_zero_is_near_identity(gradient_linear: np.ndarray) -> None:
    out = SharpenOp(amount=0.0, radius=1.0).apply(gradient_linear, CTX)
    assert out.shape == gradient_linear.shape
    # 8-bit round-trip inside the op introduces small quantization error.
    assert np.allclose(out, gradient_linear, atol=0.01)


def test_sharpen_changes_step_edge() -> None:
    img = np.zeros((32, 32, 3), dtype=np.float32)
    img[:, 16:] = 1.0
    out = SharpenOp(amount=150.0, radius=1.0).apply(img, CTX)
    assert out.shape == img.shape
    assert not np.allclose(out, img)
