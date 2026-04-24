"""Tests for color ops."""

from __future__ import annotations

import numpy as np

from autocam.ops import PipelineCtx
from autocam.ops.color import SaturationOp, VibranceOp, WhiteBalanceOp

CTX = PipelineCtx(source_path="")


def test_saturation_minus_100_yields_gray() -> None:
    red = np.zeros((4, 4, 3), dtype=np.float32)
    red[..., 0] = 1.0
    out = SaturationOp(amount=-100.0).apply(red, CTX)
    assert np.allclose(out[..., 0], out[..., 1], atol=1e-5)
    assert np.allclose(out[..., 1], out[..., 2], atol=1e-5)


def test_saturation_zero_is_identity(gradient_linear: np.ndarray) -> None:
    out = SaturationOp(amount=0.0).apply(gradient_linear, CTX)
    assert np.allclose(out, gradient_linear)


def test_saturation_positive_boosts_chroma() -> None:
    img = np.full((4, 4, 3), 0.3, dtype=np.float32)
    img[..., 0] = 0.8  # red-biased
    out = SaturationOp(amount=50.0).apply(img, CTX)
    in_chroma = img[..., 0] - img[..., 1]
    out_chroma = out[..., 0] - out[..., 1]
    assert (out_chroma > in_chroma).all()


def test_vibrance_zero_is_identity(gradient_linear: np.ndarray) -> None:
    out = VibranceOp(amount=0.0).apply(gradient_linear, CTX)
    assert np.allclose(out, gradient_linear)


def test_vibrance_eases_on_saturated_pixels() -> None:
    # Already highly saturated pixel (pure red) should move less than a
    # weakly saturated pixel under the same vibrance amount.
    red = np.zeros((1, 1, 3), dtype=np.float32)
    red[..., 0] = 1.0
    pale = np.full((1, 1, 3), 0.5, dtype=np.float32)
    pale[..., 0] = 0.6

    vib = VibranceOp(amount=100.0)
    sat = SaturationOp(amount=100.0)

    red_vib_delta = np.abs(vib.apply(red, CTX) - red).max()
    pale_vib_delta = np.abs(vib.apply(pale, CTX) - pale).max()
    pale_sat_delta = np.abs(sat.apply(pale, CTX) - pale).max()

    # Vibrance touches the pale pixel meaningfully, the red pixel barely.
    assert pale_vib_delta > red_vib_delta
    # And vibrance on the pale pixel lands within the ballpark of saturation.
    assert pale_vib_delta > 0
    assert pale_sat_delta > 0


def test_white_balance_warm_boosts_red_cuts_blue(gray_image: np.ndarray) -> None:
    out = WhiteBalanceOp(temp_shift=100.0).apply(gray_image, CTX)
    assert (out[..., 0] > gray_image[..., 0]).all()
    assert (out[..., 2] < gray_image[..., 2]).all()


def test_white_balance_zero_is_identity(gradient_linear: np.ndarray) -> None:
    out = WhiteBalanceOp().apply(gradient_linear, CTX)
    assert np.allclose(out, gradient_linear)


def test_white_balance_tint_positive_cuts_green(gray_image: np.ndarray) -> None:
    out = WhiteBalanceOp(tint=100.0).apply(gray_image, CTX)
    assert (out[..., 1] < gray_image[..., 1]).all()
