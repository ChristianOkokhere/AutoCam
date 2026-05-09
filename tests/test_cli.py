"""Tests for the CLI."""

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


def test_cli_no_args_launches_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path | None] = []

    def fake_run(image_path: Path | None = None) -> None:
        calls.append(image_path)

    monkeypatch.setattr("autocam.tui.screen.run", fake_run)
    code = main([])
    assert code == 0
    assert calls == [None]


def test_cli_path_arg_launches_tui_with_image(
    fixture_jpeg: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path | None] = []

    def fake_run(image_path: Path | None = None) -> None:
        calls.append(image_path)

    monkeypatch.setattr("autocam.tui.screen.run", fake_run)
    code = main([str(fixture_jpeg)])
    assert code == 0
    assert calls == [fixture_jpeg.expanduser()]


def test_cli_path_arg_missing_file_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main([str(tmp_path / "does-not-exist.jpg")])
    captured = capsys.readouterr()
    assert code == 2
    assert "no such file" in captured.err
