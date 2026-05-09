"""Smoke tests — prove the package imports and the entrypoint runs."""

from __future__ import annotations

import pytest

import autocam
from autocam.__main__ import main


def test_version_is_set() -> None:
    assert isinstance(autocam.__version__, str)
    assert autocam.__version__.count(".") >= 2


def test_main_version_flag_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--version"])
    captured = capsys.readouterr()
    assert code == 0
    assert autocam.__version__ in captured.out
