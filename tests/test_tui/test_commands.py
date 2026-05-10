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


def test_parse_critique_with_text() -> None:
    from autocam.tui.commands import CritiqueCommand

    cmd = parse_command("/critique focus on the skin tones")
    assert isinstance(cmd, CritiqueCommand)
    assert cmd.text == "focus on the skin tones"


def test_parse_critique_without_text() -> None:
    from autocam.tui.commands import CritiqueCommand

    cmd = parse_command("/critique")
    assert isinstance(cmd, CritiqueCommand)
    assert cmd.text == ""


def test_parse_mask_show_with_target() -> None:
    from autocam.tui.commands import MaskShowCommand

    cmd = parse_command(":mask show abc123")
    assert isinstance(cmd, MaskShowCommand)
    assert cmd.target == "abc123"


def test_parse_mask_show_without_target() -> None:
    from autocam.tui.commands import MaskShowCommand

    cmd = parse_command(":mask show")
    assert isinstance(cmd, MaskShowCommand)
    assert cmd.target == ""


def test_parse_mask_hide() -> None:
    from autocam.tui.commands import MaskHideCommand

    cmd = parse_command(":mask hide")
    assert isinstance(cmd, MaskHideCommand)


def test_parse_mask_unknown_subcommand_errors() -> None:
    with pytest.raises(CommandError, match="show"):
        parse_command(":mask blarp")


def test_parse_mask_no_subcommand_errors() -> None:
    with pytest.raises(CommandError, match="show"):
        parse_command(":mask")


def test_parse_batch_apply_basic() -> None:
    from autocam.tui.commands import BatchApplyCommand

    cmd = parse_command(":batch apply edits.json '*.arw'")
    assert isinstance(cmd, BatchApplyCommand)
    assert cmd.stack_path == Path("edits.json")
    assert cmd.glob == "*.arw"
    assert cmd.out_template == ""


def test_parse_batch_apply_with_template() -> None:
    from autocam.tui.commands import BatchApplyCommand

    cmd = parse_command(":batch apply edits.json '*.dng' '{stem}_done.jpg'")
    assert isinstance(cmd, BatchApplyCommand)
    assert cmd.out_template == "{stem}_done.jpg"


def test_parse_batch_apply_too_few_args_errors() -> None:
    with pytest.raises(CommandError, match="apply"):
        parse_command(":batch apply edits.json")


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
