"""Tests for curve ops."""

from __future__ import annotations

import numpy as np

from autocam.ops import PipelineCtx
from autocam.ops.curve import RgbCurveOp

CTX = PipelineCtx(source_path="")


def test_identity_curve_is_noop(gradient_linear: np.ndarray) -> None:
    out = RgbCurveOp(points=[[0.0, 0.0], [1.0, 1.0]]).apply(gradient_linear, CTX)
    assert np.allclose(out, gradient_linear, atol=1e-4)


def test_curve_lifts_midtones(gradient_linear: np.ndarray) -> None:
    curve = RgbCurveOp(points=[[0.0, 0.0], [0.5, 0.8], [1.0, 1.0]])
    out = curve.apply(gradient_linear, CTX)
    assert (out > gradient_linear + 1e-4).any()


def test_curve_single_channel_isolation() -> None:
    img = np.full((4, 4, 3), 0.5, dtype=np.float32)
    curve = RgbCurveOp(points=[[0.0, 0.0], [0.5, 0.8], [1.0, 1.0]], channel="r")
    out = curve.apply(img, CTX)
    assert not np.allclose(out[..., 0], img[..., 0])
    assert np.allclose(out[..., 1], img[..., 1], atol=1e-4)
    assert np.allclose(out[..., 2], img[..., 2], atol=1e-4)
