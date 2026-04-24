"""Tests for the CLI `apply` subcommand."""

from __future__ import annotations

from pathlib import Path

import pytest

from autocam.cli import main
from autocam.ops.tone import ExposureOp
from autocam.pipeline.stack import EditStack


def test_cli_apply_writes_output(fixture_jpeg: Path, tmp_path: Path) -> None:
    stack_path = tmp_path / "stack.json"
    out_path = tmp_path / "out.jpg"

    s = EditStack(source=str(fixture_jpeg))
    s.append(ExposureOp(ev=0.5))
    s.save(stack_path)

    code = main(
        [
            "apply",
            "--stack",
            str(stack_path),
            "--in",
            str(fixture_jpeg),
            "--out",
            str(out_path),
        ]
    )
    assert code == 0
    assert out_path.exists()


def test_cli_no_args_prints_banner(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([])
    captured = capsys.readouterr()
    assert code == 0
    assert "autocam" in captured.out.lower()
    assert "photo editor" in captured.out.lower()
