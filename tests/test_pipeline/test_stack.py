"""Tests for EditStack serialization + round-trips."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autocam.ops.curve import RgbCurveOp
from autocam.ops.tone import ExposureOp, ShadowsOp
from autocam.pipeline.stack import EditStack, source_hash


def test_stack_round_trip() -> None:
    s = EditStack(source="foo.jpg")
    s.append(ExposureOp(ev=0.5))
    s.append(ShadowsOp(amount=30.0))
    s.append(RgbCurveOp(points=[[0.0, 0.0], [0.5, 0.6], [1.0, 1.0]], channel="rgb"))

    text = s.to_json()
    s2 = EditStack.from_json(text)

    assert s2.source == "foo.jpg"
    assert len(s2.ops) == 3
    assert isinstance(s2.ops[0], ExposureOp)
    assert s2.ops[0].ev == 0.5
    assert isinstance(s2.ops[1], ShadowsOp)
    assert s2.ops[1].amount == 30.0
    assert isinstance(s2.ops[2], RgbCurveOp)
    assert s2.ops[2].channel == "rgb"


def test_stack_json_shape() -> None:
    s = EditStack(source="foo.jpg")
    s.append(ExposureOp(ev=0.5))
    data = json.loads(s.to_json())
    assert data["version"] == 1
    assert data["source"] == "foo.jpg"
    assert data["ops"][0]["op"] == "tone.exposure"
    assert data["ops"][0]["params"]["ev"] == 0.5


def test_stack_save_load(tmp_path: Path) -> None:
    s = EditStack(source="foo.jpg")
    s.append(ExposureOp(ev=0.5))
    p = tmp_path / "stack.json"
    s.save(p)
    s2 = EditStack.load(p)
    assert s2.ops[0].ev == 0.5


def test_stack_rejects_wrong_version() -> None:
    data = {"version": 999, "source": "foo.jpg", "ops": []}
    with pytest.raises(ValueError, match="Unsupported stack version"):
        EditStack.from_dict(data)


def test_source_hash_deterministic(tmp_path: Path) -> None:
    p = tmp_path / "file.bin"
    p.write_bytes(b"hello world")
    h1 = source_hash(p)
    h2 = source_hash(p)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_stack_round_trip_with_mask_field() -> None:
    """Phase 6a: an op carrying a `mask` reference must round-trip via JSON."""
    from autocam.ops.masks import LuminosityMaskOp

    s = EditStack(source="foo.jpg")
    mask_op = LuminosityMaskOp(range="highs", feather=0.0)
    s.append(mask_op)
    s.append(ExposureOp(ev=-0.5, mask=mask_op.id))

    text = s.to_json()
    data = json.loads(text)
    assert data["ops"][0]["op"] == "mask.luminosity"
    assert "mask" not in data["ops"][0]  # mask op has no mask field in JSON
    assert data["ops"][1]["op"] == "tone.exposure"
    assert data["ops"][1]["mask"] == mask_op.id

    s2 = EditStack.from_json(text)
    assert s2.ops[1].mask == mask_op.id


def test_legacy_stack_without_mask_field_round_trips() -> None:
    """Stacks written before Phase 6a have no `mask` key — must still load."""
    legacy = {
        "version": 1,
        "source": "foo.jpg",
        "ops": [{"id": "abc", "op": "tone.exposure", "params": {"ev": 0.5}}],
    }
    s = EditStack.from_dict(legacy)
    assert s.ops[0].mask is None
    assert s.ops[0].ev == 0.5
