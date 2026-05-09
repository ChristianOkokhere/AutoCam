"""Tests for the TUI command parser + op builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from autocam.ops.tone import ExposureOp
from autocam.tui.commands import (
    AddCommand,
    ChatMessage,
    CommandError,
    OpenCommand,
    QuitCommand,
    RedoCommand,
    UndoCommand,
    build_op,
    parse_command,
)


def test_parse_chat_message_passes_through() -> None:
    cmd = parse_command("warm the highlights")
    assert isinstance(cmd, ChatMessage)
    assert cmd.text == "warm the highlights"
    assert cmd.deep is False


def test_parse_deep_chat_message() -> None:
    cmd = parse_command("/deep make the sky pop")
    assert isinstance(cmd, ChatMessage)
    assert cmd.text == "make the sky pop"
    assert cmd.deep is True


def test_parse_deep_without_message_errors() -> None:
    with pytest.raises(CommandError):
        parse_command("/deep")


def test_parse_add_with_params() -> None:
    cmd = parse_command(":add tone.exposure ev=0.5")
    assert isinstance(cmd, AddCommand)
    assert cmd.op_name == "tone.exposure"
    assert cmd.raw_params == {"ev": "0.5"}


def test_parse_add_multiple_params() -> None:
    cmd = parse_command(":add color.white_balance temp_shift=200 tint=-15")
    assert isinstance(cmd, AddCommand)
    assert cmd.raw_params == {"temp_shift": "200", "tint": "-15"}


def test_parse_undo_redo_quit() -> None:
    assert isinstance(parse_command(":undo"), UndoCommand)
    assert isinstance(parse_command(":redo"), RedoCommand)
    assert isinstance(parse_command(":quit"), QuitCommand)


def test_parse_open_expands_user() -> None:
    cmd = parse_command(":open ~/photo.jpg")
    assert isinstance(cmd, OpenCommand)
    assert cmd.path == Path("~/photo.jpg").expanduser()


def test_parse_unknown_command_errors() -> None:
    with pytest.raises(CommandError):
        parse_command(":zoom 1.5")


def test_parse_add_without_op_errors() -> None:
    with pytest.raises(CommandError):
        parse_command(":add")


def test_parse_add_bad_kv_errors() -> None:
    with pytest.raises(CommandError):
        parse_command(":add tone.exposure not-a-pair")


def test_build_op_coerces_floats() -> None:
    op = build_op("tone.exposure", {"ev": "0.3"})
    assert isinstance(op, ExposureOp)
    assert op.ev == pytest.approx(0.3)


def test_build_op_coerces_ints() -> None:
    op = build_op("export.save", {"path": "out.jpg", "format": "jpeg", "quality": "85"})
    assert op.quality == 85
    assert op.format == "jpeg"


def test_build_op_coerces_json_list() -> None:
    op = build_op("curve.rgb", {"points": "[[0, 0], [0.5, 0.6], [1, 1]]"})
    assert op.points == [[0, 0], [0.5, 0.6], [1, 1]]


def test_build_op_unknown_param_errors() -> None:
    with pytest.raises(CommandError):
        build_op("tone.exposure", {"nope": "0.5"})


def test_build_op_unknown_op_errors() -> None:
    with pytest.raises(KeyError):
        build_op("nonsense.op", {})
