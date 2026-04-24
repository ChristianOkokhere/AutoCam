"""Tests for the pipeline executor."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from autocam.io.image import load_image
from autocam.ops.export_ops import ExportSaveOp
from autocam.ops.tone import ExposureOp
from autocam.pipeline.executor import PREVIEW_MAX_EDGE, Pipeline, run_stack
from autocam.pipeline.stack import EditStack


def test_run_stack_applies_ops(fixture_jpeg: Path) -> None:
    s = EditStack(source=str(fixture_jpeg))
    s.append(ExposureOp(ev=1.0))
    out = run_stack(s)
    original = load_image(fixture_jpeg)
    assert out.shape == original.shape
    assert out.mean() > original.mean()


def test_export_save_writes_file(fixture_jpeg: Path, tmp_path: Path) -> None:
    target = tmp_path / "out.jpg"
    s = EditStack(source=str(fixture_jpeg))
    s.append(ExposureOp(ev=0.5))
    s.append(ExportSaveOp(path=str(target), format="jpeg", quality=85))
    run_stack(s)
    assert target.exists()
    with Image.open(target) as im:
        assert im.size[0] > 0 and im.size[1] > 0


def test_preview_flag_runs(fixture_jpeg: Path) -> None:
    s = EditStack(source=str(fixture_jpeg))
    out = run_stack(s, preview=True)
    assert max(out.shape[:2]) <= PREVIEW_MAX_EDGE


def test_pipeline_builder_chain(fixture_jpeg: Path) -> None:
    p = Pipeline(fixture_jpeg).add(ExposureOp(ev=0.25))
    out = p.run()
    assert isinstance(out, np.ndarray)
    assert out.ndim == 3
