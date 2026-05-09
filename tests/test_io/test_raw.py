"""Tests for the RAW loader and the load-dispatcher.

We don't bundle real RAW fixtures (binary blobs in git; per-camera quirks).
Instead we mock ``rawpy.imread`` to verify the wrapper calls postprocess
with the right knobs and converts the result to linear-sRGB float32.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rawpy

from autocam.io import load_any
from autocam.io.raw import RAW_EXTENSIONS, is_raw_path, load_raw


class _FakeRaw:
    """Mimics the context-manager rawpy returns from ``imread``."""

    def __init__(self, *, height: int = 8, width: int = 12) -> None:
        self.height = height
        self.width = width
        self.last_kwargs: dict[str, object] = {}

    def __enter__(self) -> _FakeRaw:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def postprocess(self, **kwargs: object) -> np.ndarray:
        self.last_kwargs = kwargs
        h = self.height // 2 if kwargs.get("half_size") else self.height
        w = self.width // 2 if kwargs.get("half_size") else self.width
        return np.full((h, w, 3), 32_768, dtype=np.uint16)


@pytest.fixture
def fake_raw(monkeypatch: pytest.MonkeyPatch) -> _FakeRaw:
    fake = _FakeRaw()
    monkeypatch.setattr("autocam.io.raw.rawpy.imread", lambda _path: fake)
    return fake


def test_is_raw_path_canonical_extensions() -> None:
    for ext in (".arw", ".cr2", ".cr3", ".dng", ".nef", ".orf", ".raf", ".rw2"):
        assert is_raw_path(Path("photo" + ext))
        assert is_raw_path(Path("PHOTO" + ext.upper()))
    assert not is_raw_path(Path("photo.jpg"))
    assert not is_raw_path(Path("photo.png"))
    assert not is_raw_path(Path("photo"))  # no extension


def test_raw_extensions_are_lowercase() -> None:
    assert all(ext == ext.lower() for ext in RAW_EXTENSIONS)


def test_load_raw_returns_linear_float32_in_unit_range(fake_raw: _FakeRaw) -> None:
    arr = load_raw(Path("/fake.arw"))
    assert arr.dtype == np.float32
    assert arr.shape == (8, 12, 3)
    # 32768 / 65535 ≈ 0.5
    assert 0.49 < float(arr[0, 0, 0]) < 0.51


def test_load_raw_passes_canonical_postprocess_args(fake_raw: _FakeRaw) -> None:
    load_raw(Path("/fake.arw"))
    kw = fake_raw.last_kwargs
    assert kw["output_bps"] == 16
    assert kw["use_camera_wb"] is True
    assert kw["no_auto_bright"] is True
    assert kw["gamma"] == (1.0, 1.0)
    assert kw["output_color"] == rawpy.ColorSpace.sRGB
    assert kw["demosaic_algorithm"] == rawpy.DemosaicAlgorithm.AHD
    assert kw["half_size"] is False


def test_load_raw_preview_uses_half_size(fake_raw: _FakeRaw) -> None:
    arr = load_raw(Path("/fake.arw"), preview=True)
    assert fake_raw.last_kwargs["half_size"] is True
    # Half-size keeps the 16-bit output_bps so we still have headroom.
    assert fake_raw.last_kwargs["output_bps"] == 16
    # Half of 8x12 → 4x6.
    assert arr.shape == (4, 6, 3)


def test_load_any_dispatches_raw_to_rawpy(fake_raw: _FakeRaw) -> None:
    arr = load_any("/fake.arw")
    assert arr.shape == (8, 12, 3)
    assert fake_raw.last_kwargs  # postprocess was called → went via load_raw


def test_load_any_dispatches_raster_to_pil(fixture_jpeg: Path) -> None:
    # No fake_raw fixture → rawpy must NOT be called for JPEG.
    arr = load_any(fixture_jpeg)
    assert arr.dtype == np.float32
    assert arr.ndim == 3
    assert arr.shape[-1] == 3
