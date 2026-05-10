"""Tests for the auto-generated Anthropic tool surface."""

from __future__ import annotations

import re

import pytest

from autocam.llm.tools import (
    all_tool_specs,
    from_tool_name,
    op_tool_spec,
    to_tool_name,
)
from autocam.ops import registered_ops
from autocam.ops.color import WhiteBalanceOp
from autocam.ops.curve import RgbCurveOp
from autocam.ops.export_ops import ExportSaveOp
from autocam.ops.tone import ExposureOp

TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def test_tool_name_round_trip() -> None:
    assert to_tool_name("tone.exposure") == "tone_exposure"
    assert from_tool_name("tone_exposure") == "tone.exposure"


def test_from_tool_name_unknown_raises() -> None:
    with pytest.raises(KeyError):
        from_tool_name("not_a_real_op")


def test_exposure_tool_spec_shape() -> None:
    spec = op_tool_spec(ExposureOp)
    assert spec["name"] == "tone_exposure"
    assert spec["description"]  # non-empty
    schema = spec["input_schema"]
    assert schema["type"] == "object"
    assert schema["properties"]["ev"]["type"] == "number"
    assert schema["properties"]["ev"]["default"] == 0.0
    assert schema["required"] == []


def test_export_save_int_and_literal() -> None:
    spec = op_tool_spec(ExportSaveOp)
    props = spec["input_schema"]["properties"]
    assert props["quality"]["type"] == "integer"
    assert props["format"]["enum"] == ["jpeg", "png", "tiff"]
    assert props["format"]["type"] == "string"
    assert props["path"]["type"] == "string"


def test_white_balance_two_floats() -> None:
    spec = op_tool_spec(WhiteBalanceOp)
    props = spec["input_schema"]["properties"]
    assert props["temp_shift"]["type"] == "number"
    assert props["tint"]["type"] == "number"


def test_rgb_curve_nested_list() -> None:
    spec = op_tool_spec(RgbCurveOp)
    props = spec["input_schema"]["properties"]
    points = props["points"]
    assert points["type"] == "array"
    assert points["items"]["type"] == "array"
    assert points["items"]["items"]["type"] == "number"
    # Default from the dataclass factory:
    assert points["default"] == [[0.0, 0.0], [1.0, 1.0]]


def test_all_tool_specs_covers_registry() -> None:
    specs = all_tool_specs()
    spec_names = {s["name"] for s in specs}
    expected = {to_tool_name(op_name) for op_name in registered_ops()}
    assert spec_names == expected


def test_all_tool_names_are_anthropic_legal() -> None:
    for spec in all_tool_specs():
        assert TOOL_NAME_RE.match(spec["name"]), spec["name"]
        assert len(spec["description"]) <= 1024


def test_adjustment_op_exposes_mask_param() -> None:
    spec = op_tool_spec(ExposureOp)
    props = spec["input_schema"]["properties"]
    assert "mask" in props
    assert props["mask"]["type"] == "string"
    assert props["mask"]["default"] is None
    assert "mask" in props["mask"]["description"].lower()


def test_mask_op_hides_its_own_mask_param() -> None:
    from autocam.ops.masks import LuminosityMaskOp

    spec = op_tool_spec(LuminosityMaskOp)
    props = spec["input_schema"]["properties"]
    assert "mask" not in props


def test_mask_op_tool_surface_includes_three_masks() -> None:
    names = {s["name"] for s in all_tool_specs()}
    assert {"mask_luminosity", "mask_color_range", "mask_invert"} <= names
