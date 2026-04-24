"""Phase 0 smoke tests — prove the package imports and the entrypoint runs."""

from __future__ import annotations

import pytest

import autocam
from autocam.__main__ import main


def test_version_is_set() -> None:
    assert isinstance(autocam.__version__, str)
    assert autocam.__version__.count(".") >= 2


def test_main_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    result = main([])
    captured = capsys.readouterr()
    assert result == 0
    assert "autocam" in captured.out.lower()
    assert "photo editor" in captured.out.lower()
