"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from autocam.pipeline.color import linear_to_srgb


@pytest.fixture
def gradient_linear() -> np.ndarray:
    """Linear-sRGB gradient image: R varies by column, G by row, B constant."""
    height, width = 64, 64
    xs = np.linspace(0.0, 1.0, width, dtype=np.float32)
    ys = np.linspace(0.0, 1.0, height, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    return np.stack([xx, yy, np.full_like(xx, 0.5)], axis=-1).astype(np.float32)


@pytest.fixture
def gray_image() -> np.ndarray:
    """Uniform mid-gray in linear sRGB."""
    return np.full((32, 32, 3), 0.5, dtype=np.float32)


@pytest.fixture
def fixture_jpeg(tmp_path: Path, gradient_linear: np.ndarray) -> Path:
    """Write the gradient fixture to disk as a JPEG for executor/CLI tests."""
    display = linear_to_srgb(gradient_linear)
    arr8 = np.clip(display * 255.0, 0, 255).astype(np.uint8)
    path = tmp_path / "fixture.jpg"
    Image.fromarray(arr8).save(path, quality=95)
    return path
