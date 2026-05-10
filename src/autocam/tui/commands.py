"""Command-line parser for the TUI's chat input.

The chat pane accepts colon-prefixed commands so we can drive the editor by
hand before the LLM is wired in. Grammar::

    :add <op.name> [key=value ...]
    :undo
    :redo
    :open <path>
    :quit

Anything not starting with ``:`` is treated as free chat (echoed back today,
sent to Claude in Phase 3). Param values are coerced to each op's declared
field type — ``int``, ``float``, ``bool`` are converted; everything else
(including ``Literal`` choices) is passed through as a string, with JSON
fallback for values that look like lists or objects.
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_type_hints

from autocam.ops import Op, get_op_class


@dataclass
class AddCommand:
    op_name: str
    raw_params: dict[str, str]


@dataclass
class UndoCommand:
    pass


@dataclass
class RedoCommand:
    pass


@dataclass
class OpenCommand:
    path: Path


@dataclass
class QuitCommand:
    pass


@dataclass
class ChatMessage:
    text: str
    deep: bool = False  # ``/deep <msg>`` → escalate next turn to Opus


@dataclass
class CritiqueCommand:
    """``/critique [thoughts]`` — text-only Claude pass, stack untouched."""

    text: str = ""


@dataclass
class MaskShowCommand:
    """``:mask show [target]`` — overlay a mask on the preview.

    ``target`` is either a mask op id (full or prefix), the literal ``last``
    for the most recently appended mask op, or empty (treated as ``last``).
    """

    target: str = ""


@dataclass
class MaskHideCommand:
    """``:mask hide`` — clear any active mask overlay."""


@dataclass
class BatchApplyCommand:
    """``:batch apply <stack> <glob> [<out_template>]``.

    Applies a saved edit stack to every file matching ``glob`` and writes
    each through ``out_template`` (default: ``{stem}_autocam.jpg``).
    """

    stack_path: Path
    glob: str
    out_template: str = ""


@dataclass
class ExportCommand:
    """``:export <preset> [<out_path>]`` — run the live stack to disk."""

    preset: str
    out_path: Path | None = None


@dataclass
class HelpCommand:
    """``:help`` (or the ``?`` keybinding) — dump the command reference."""


Command = (
    AddCommand
    | UndoCommand
    | RedoCommand
    | OpenCommand
    | QuitCommand
    | ChatMessage
    | CritiqueCommand
    | MaskShowCommand
    | MaskHideCommand
    | BatchApplyCommand
    | ExportCommand
    | HelpCommand
)


class CommandError(ValueError):
    """Raised when a colon command cannot be parsed."""


def parse_command(line: str) -> Command:
    line = line.strip()
    if not line:
        raise CommandError("empty input")
    if line.startswith("/deep"):
        rest = line[len("/deep") :].strip()
        if not rest:
            raise CommandError("/deep needs a message: `/deep make the sky pop`")
        return ChatMessage(text=rest, deep=True)
    if line.startswith("/critique"):
        rest = line[len("/critique") :].strip()
        return CritiqueCommand(text=rest)
    if not line.startswith(":"):
        return ChatMessage(text=line)

    try:
        tokens = shlex.split(line[1:])
    except ValueError as exc:
        raise CommandError(f"could not tokenize: {exc}") from exc
    if not tokens:
        raise CommandError("empty command")

    verb, *rest = tokens
    if verb == "add":
        if not rest:
            raise CommandError(":add needs an op name (e.g. `:add tone.exposure ev=0.3`)")
        op_name, *kvs = rest
        params: dict[str, str] = {}
        for kv in kvs:
            if "=" not in kv:
                raise CommandError(f"expected key=value, got {kv!r}")
            key, value = kv.split("=", 1)
            params[key] = value
        return AddCommand(op_name=op_name, raw_params=params)
    if verb == "undo":
        return UndoCommand()
    if verb == "redo":
        return RedoCommand()
    if verb == "open":
        if not rest:
            raise CommandError(":open needs a path")
        return OpenCommand(path=Path(rest[0]).expanduser())
    if verb == "quit":
        return QuitCommand()
    if verb == "mask":
        if not rest:
            raise CommandError(":mask needs `show [target]` or `hide`")
        sub = rest[0]
        if sub == "show":
            target = rest[1] if len(rest) > 1 else ""
            return MaskShowCommand(target=target)
        if sub == "hide":
            return MaskHideCommand()
        raise CommandError(f":mask {sub!r} — expected `show` or `hide`")
    if verb == "batch":
        if len(rest) < 3 or rest[0] != "apply":
            raise CommandError(":batch apply <stack.json> <glob> [<out_template>]")
        stack_path = Path(rest[1]).expanduser()
        glob = rest[2]
        out_template = rest[3] if len(rest) > 3 else ""
        return BatchApplyCommand(stack_path=stack_path, glob=glob, out_template=out_template)
    if verb == "export":
        if not rest:
            raise CommandError(":export needs a preset (web | print)")
        preset = rest[0]
        out_path = Path(rest[1]).expanduser() if len(rest) > 1 else None
        return ExportCommand(preset=preset, out_path=out_path)
    if verb == "help":
        return HelpCommand()
    raise CommandError(f"unknown command: :{verb}")


def build_op(op_name: str, raw_params: dict[str, str]) -> Op:
    """Look up an op class and coerce ``raw_params`` to its declared types."""
    op_cls = get_op_class(op_name)
    hints = get_type_hints(op_cls)
    coerced: dict[str, Any] = {}
    for key, value in raw_params.items():
        if key not in hints:
            raise CommandError(f"{op_name} has no parameter {key!r}")
        coerced[key] = _coerce(value, hints[key])
    return op_cls(**coerced)


def _coerce(value: str, field_type: Any) -> Any:
    if field_type is int:
        return int(value)
    if field_type is float:
        return float(value)
    if field_type is bool:
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    stripped = value.strip()
    if stripped.startswith(("[", "{")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise CommandError(f"could not parse JSON value {value!r}: {exc}") from exc
    return value
