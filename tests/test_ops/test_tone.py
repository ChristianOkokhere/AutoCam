"""Tests for tonal ops."""

from __future__ import annotations

import numpy as np

from autocam.ops import PipelineCtx
from autocam.ops.tone import (
    BlacksOp,
    ContrastOp,
    ExposureOp,
    HighlightsOp,
    ShadowsOp,
    WhitesOp,
)
from autocam.pipeline.color import linear_to_srgb

CTX = PipelineCtx(source_path="")


def test_exposure_plus_one_doubles(gray_image: np.ndarray) -> None:
    out = ExposureOp(ev=1.0).apply(gray_image, CTX)
    assert np.allclose(out, gray_image * 2.0)


def test_exposure_zero_is_identity(gradient_linear: np.ndarray) -> None:
    out = ExposureOp(ev=0.0).apply(gradient_linear, CTX)
    assert np.allclose(out, gradient_linear)


def test_contrast_zero_is_identity(gradient_linear: np.ndarray) -> None:
    out = ContrastOp(amount=0.0).apply(gradient_linear, CTX)
    assert np.allclose(out, gradient_linear, atol=1e-4)


def test_contrast_positive_pushes_tones_apart(gradient_linear: np.ndarray) -> None:
    out = ContrastOp(amount=50.0).apply(gradient_linear, CTX)
    in_display = linear_to_srgb(gradient_linear)
    out_display = linear_to_srgb(out)
    above = in_display > 0.55
    below = in_display < 0.45
    assert (out_display[above] >= in_display[above] - 1e-4).all()
    assert (out_display[below] <= in_display[below] + 1e-4).all()


def test_highlights_negative_darkens_bright(gradient_linear: np.ndarray) -> None:
    out = HighlightsOp(amount=-100.0).apply(gradient_linear, CTX)
    # Top-right corner: R=1, G=0, B=0.5 in linear → high display in R.
    assert out[0, -1, 0] < gradient_linear[0, -1, 0]


def test_shadows_positive_lifts_dark(gradient_linear: np.ndarray) -> None:
    out = ShadowsOp(amount=100.0).apply(gradient_linear, CTX)
    # Top-left corner: R=0, G=0 → dark tones, should lift.
    assert out[0, 0, 0] > gradient_linear[0, 0, 0] - 1e-6
    assert out[0, 0, 1] > gradient_linear[0, 0, 1] - 1e-6


def test_whites_zero_is_identity(gradient_linear: np.ndarray) -> None:
    out = WhitesOp(amount=0.0).apply(gradient_linear, CTX)
    assert np.allclose(out, gradient_linear, atol=1e-4)


def test_blacks_zero_is_identity(gradient_linear: np.ndarray) -> None:
    out = BlacksOp(amount=0.0).apply(gradient_linear, CTX)
    assert np.allclose(out, gradient_linear, atol=1e-4)


def test_whites_positive_pushes_near_white_up() -> None:
    # A patch that sits near the white point.
    img = np.full((4, 4, 3), 0.95, dtype=np.float32)
    out = WhitesOp(amount=100.0).apply(img, CTX)
    assert (out >= img).all()
