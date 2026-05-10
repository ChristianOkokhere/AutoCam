"""Tests for the structure ops (resize / pad / border / text / watermark)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from autocam.ops import (
    BorderOp,
    PadOp,
    PipelineCtx,
    ResizeOp,
    TextOp,
    WatermarkOp,
)
from autocam.ops.structure import _parse_color
from autocam.pipeline.color import linear_to_srgb


def _ctx() -> PipelineCtx:
    return PipelineCtx(source_path="<mem>")


def _solid(h: int, w: int, value: float) -> np.ndarray:
    return np.full((h, w, 3), value, dtype=np.float32)


def test_resize_scale_halves_dimensions() -> None:
    img = _solid(40, 60, 0.5)
    out = ResizeOp(scale=0.5).apply(img, _ctx())
    assert out.shape == (20, 30, 3)


def test_resize_width_keeps_aspect() -> None:
    img = _solid(40, 60, 0.5)
    out = ResizeOp(width=30).apply(img, _ctx())
    # 30/60 = 0.5 → height halves to 20.
    assert out.shape == (20, 30, 3)


def test_resize_height_keeps_aspect() -> None:
    img = _solid(40, 60, 0.5)
    out = ResizeOp(height=10).apply(img, _ctx())
    # 10/40 = 0.25 → width = 60 * 0.25 = 15.
    assert out.shape == (10, 15, 3)


def test_resize_no_dim_raises() -> None:
    img = _solid(10, 10, 0.5)
    with pytest.raises(ValueError, match="needs scale"):
        ResizeOp().apply(img, _ctx())


def test_pad_grows_canvas_with_color() -> None:
    img = _solid(20, 20, 0.5)
    out = PadOp(top=5, right=10, bottom=15, left=20, color="#ff0000").apply(img, _ctx())
    assert out.shape == (40, 50, 3)
    # Top-left pixel should be the pad colour (red, in linear sRGB).
    display = linear_to_srgb(out)
    assert display[0, 0, 0] > 0.95
    assert display[0, 0, 1] < 0.05
    assert display[0, 0, 2] < 0.05


def test_border_uses_short_edge_percentage() -> None:
    img = _solid(50, 100, 0.5)
    out = BorderOp(width_pct=10.0, color="#00ff00").apply(img, _ctx())
    # 10 % of 50 = 5 px each side → 60 x 110.
    assert out.shape == (60, 110, 3)
    display = linear_to_srgb(out)
    # Outer corner is the border colour (green).
    assert display[0, 0, 1] > 0.95


def test_border_width_pct_zero_passes_through() -> None:
    img = _solid(20, 20, 0.5)
    out = BorderOp(width_pct=0.0).apply(img, _ctx())
    assert out.shape == img.shape
    np.testing.assert_allclose(out, img, atol=1e-6)


def test_text_op_writes_pixels_into_canvas() -> None:
    img = _solid(80, 200, 0.0)  # black canvas
    out = TextOp(content="OK", size=24, color="#ffffff", anchor="mc").apply(img, _ctx())
    display = linear_to_srgb(out)
    # Some pixel near the centre should now be bright (the glyph fill).
    centre = display[30:50, 80:120]
    assert centre.max() > 0.5


def test_text_op_empty_content_passes_through() -> None:
    img = _solid(20, 20, 0.5)
    out = TextOp(content="").apply(img, _ctx())
    np.testing.assert_allclose(out, img, atol=1e-6)


def test_watermark_op_alpha_composites(tmp_path: Path) -> None:
    # Create a blue 16x16 watermark with an alpha channel.
    wm_path = tmp_path / "wm.png"
    wm = Image.new("RGBA", (16, 16), (0, 0, 255, 255))
    wm.save(wm_path)

    img = _solid(80, 80, 0.0)
    out = WatermarkOp(
        path=str(wm_path),
        scale_pct=0.0,  # do not rescale — keep 16x16
        opacity=1.0,
        anchor="br",
        x_off=4,
        y_off=4,
    ).apply(img, _ctx())

    display = linear_to_srgb(out)
    # Bottom-right corner should be blue (where the wm is pasted).
    assert display[-5, -5, 2] > 0.9
    # Top-left should still be black.
    assert display[2, 2].max() < 0.05


def test_watermark_op_missing_path_raises() -> None:
    img = _solid(20, 20, 0.5)
    with pytest.raises(ValueError, match="path"):
        WatermarkOp(path="").apply(img, _ctx())


def test_color_parser_accepts_hex_and_named() -> None:
    assert _parse_color("#ffffff") == (255, 255, 255, 255)
    assert _parse_color("#00ff0080")[:3] == (0, 255, 0)
    assert _parse_color("white") == (255, 255, 255, 255)
    assert _parse_color("red")[0] == 255


def test_struct_ops_registered_in_tool_surface() -> None:
    from autocam.llm.tools import all_tool_specs

    names = {s["name"] for s in all_tool_specs()}
    assert {
        "struct_resize",
        "struct_pad",
        "struct_border",
        "struct_text",
        "struct_watermark",
    } <= names
