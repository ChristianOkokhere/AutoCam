"""Tests for the multi-image batch runner."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from autocam.ops.tone import ExposureOp
from autocam.pipeline.batch import (
    DEFAULT_TEMPLATE,
    BatchResult,
    expand_inputs,
    resolve_out_template,
    run_many,
    run_one,
    stack_short_id,
)
from autocam.pipeline.color import linear_to_srgb
from autocam.pipeline.stack import EditStack


def _write_jpeg(path: Path, value: float = 0.5, size: tuple[int, int] = (32, 32)) -> Path:
    """Drop a tiny solid-grey JPEG on disk so run_stack has something to load."""
    arr = np.full((size[1], size[0], 3), value, dtype=np.float32)
    display = linear_to_srgb(arr)
    arr8 = np.clip(display * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(arr8).save(path, quality=95)
    return path


def _write_stack(path: Path, source: Path) -> Path:
    s = EditStack(source=str(source))
    s.append(ExposureOp(ev=0.5))
    s.save(path)
    return path


def test_resolve_out_template_replaces_tokens(tmp_path: Path) -> None:
    out = resolve_out_template(
        "out/{stem}_{idx}_{stack_id}.{ext}",
        source=Path("/in/photo.ARW"),
        idx=2,
        total=10,
        stack_id="abcd1234",
    )
    # idx is 1-based + zero-padded to width(total) = 2
    assert str(out) == "out/photo_03_abcd1234.arw"


def test_resolve_out_template_directory_uses_default(tmp_path: Path) -> None:
    out = resolve_out_template(
        str(tmp_path / "exports"),
        source=Path("/in/photo.dng"),
        idx=0,
        total=1,
        stack_id="x",
    )
    expected = tmp_path / "exports" / DEFAULT_TEMPLATE.replace("{stem}", "photo")
    assert out == expected


def test_run_one_writes_output(tmp_path: Path) -> None:
    src = _write_jpeg(tmp_path / "src.jpg")
    stack_path = _write_stack(tmp_path / "stack.json", src)
    out = tmp_path / "out.jpg"

    r = run_one(
        stack_path=stack_path,
        source=src,
        output=out,
        image_format="jpeg",
        idx=0,
        total=1,
    )

    assert r.ok
    assert r.output == out
    assert out.exists()
    assert r.seconds >= 0


def test_run_one_reports_failure_on_bad_source(tmp_path: Path) -> None:
    stack_path = _write_stack(tmp_path / "stack.json", tmp_path / "missing.jpg")
    r = run_one(
        stack_path=stack_path,
        source=tmp_path / "does-not-exist.jpg",
        output=tmp_path / "out.jpg",
        idx=0,
        total=1,
    )
    assert not r.ok
    assert r.error
    assert r.output is None


def test_run_many_sequential_writes_all_outputs(tmp_path: Path) -> None:
    sources = [_write_jpeg(tmp_path / f"src_{i}.jpg", value=0.2 + 0.1 * i) for i in range(3)]
    stack_path = _write_stack(tmp_path / "stack.json", sources[0])
    out_template = str(tmp_path / "out" / "{stem}_done.jpg")

    events: list[BatchResult] = []
    results = run_many(
        stack_path=stack_path,
        sources=sources,
        out_template=out_template,
        workers=1,
        on_event=events.append,
    )

    assert len(results) == 3
    assert all(r.ok for r in results)
    for r in results:
        assert r.output is not None
        assert r.output.exists()
    # idx values are 1-based and dense.
    assert [r.idx for r in results] == [1, 2, 3]
    # Events fire in source order when workers=1.
    assert [e.idx for e in events] == [1, 2, 3]


def test_run_many_collects_failures_without_aborting(tmp_path: Path) -> None:
    good = _write_jpeg(tmp_path / "good.jpg")
    bad = tmp_path / "missing.jpg"
    stack_path = _write_stack(tmp_path / "stack.json", good)

    results = run_many(
        stack_path=stack_path,
        sources=[good, bad, good],
        out_template=str(tmp_path / "{stem}_{idx}.jpg"),
        workers=1,
    )
    assert len(results) == 3
    assert results[0].ok
    assert not results[1].ok
    assert results[2].ok


def test_run_many_empty_sources_returns_empty(tmp_path: Path) -> None:
    stack_path = _write_stack(tmp_path / "stack.json", tmp_path / "x.jpg")
    assert run_many(stack_path=stack_path, sources=[]) == []


def test_stack_short_id_is_stable(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    p.write_text('{"version":1,"source":"x","ops":[]}', encoding="utf-8")
    a = stack_short_id(p)
    b = stack_short_id(p)
    assert a == b
    assert len(a) == 8


def test_expand_inputs_globs_and_dedupes(tmp_path: Path) -> None:
    a = _write_jpeg(tmp_path / "a.jpg")
    _write_jpeg(tmp_path / "b.jpg")
    out = expand_inputs([str(tmp_path / "*.jpg"), str(a)])
    assert sorted(p.name for p in out) == ["a.jpg", "b.jpg"]
    # `a` listed twice (glob + literal) → deduped.
    assert len(out) == 2


def test_expand_inputs_skips_missing_paths(tmp_path: Path) -> None:
    out = expand_inputs([str(tmp_path / "nothing-here.jpg")])
    assert out == []


def test_cli_batch_processes_glob(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from autocam.cli import main

    sources = [_write_jpeg(tmp_path / f"src_{i}.jpg") for i in range(2)]
    stack_path = _write_stack(tmp_path / "stack.json", sources[0])
    out_dir = tmp_path / "out"

    code = main(
        [
            "batch",
            "--stack",
            str(stack_path),
            "--in",
            str(tmp_path / "src_*.jpg"),
            "--out",
            str(out_dir / "{stem}.jpg"),
            "--workers",
            "1",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "2/2 succeeded" in captured.out
    assert (out_dir / "src_0.jpg").exists()
    assert (out_dir / "src_1.jpg").exists()
