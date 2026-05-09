"""Auto-generate Anthropic tool definitions from each registered Op.

The tool surface is single-sourced: every Op dataclass already declares the
shape Claude can call. We read the field types via :func:`typing.get_type_hints`
and translate them to JSONSchema, so adding an op anywhere automatically
extends the tool surface without a separate spec file to drift from.

Op names contain ``.`` (``tone.exposure``); Anthropic tool names must match
``^[a-zA-Z0-9_-]{1,64}$``, so we map ``.`` → ``_`` on the way out and reverse
the mapping when a tool_use block comes back.
"""

from __future__ import annotations

from dataclasses import MISSING, fields
from typing import Any, Literal, get_args, get_origin, get_type_hints

from autocam.ops import Op, registered_ops


def to_tool_name(op_name: str) -> str:
    """Map ``tone.exposure`` → ``tone_exposure`` for the Anthropic API."""
    return op_name.replace(".", "_")


def from_tool_name(tool_name: str, *, registry: dict[str, type[Op]] | None = None) -> str:
    """Reverse :func:`to_tool_name` against the live op registry."""
    table = registry if registry is not None else registered_ops()
    for op_name in table:
        if to_tool_name(op_name) == tool_name:
            return op_name
    raise KeyError(f"unknown tool name: {tool_name!r}")


def _type_to_schema(field_type: Any) -> dict[str, Any]:
    if field_type is int:
        return {"type": "integer"}
    if field_type is float:
        return {"type": "number"}
    if field_type is bool:
        return {"type": "boolean"}
    if field_type is str:
        return {"type": "string"}

    origin = get_origin(field_type)
    if origin is Literal:
        choices = list(get_args(field_type))
        if all(isinstance(c, str) for c in choices):
            return {"type": "string", "enum": choices}
        if all(isinstance(c, int) for c in choices):
            return {"type": "integer", "enum": choices}
        return {"enum": choices}
    if origin is list:
        (inner,) = get_args(field_type) or (Any,)
        return {"type": "array", "items": _type_to_schema(inner)}

    raise TypeError(f"unsupported field type for tool spec: {field_type!r}")


def op_tool_spec(op_cls: type[Op]) -> dict[str, Any]:
    """Return one Anthropic tool definition for an Op subclass."""
    hints = get_type_hints(op_cls)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for field_def in fields(op_cls):
        if field_def.name == "id":
            continue
        prop = _type_to_schema(hints[field_def.name])
        if field_def.default is not MISSING:
            prop["default"] = field_def.default
        elif field_def.default_factory is not MISSING:  # type: ignore[misc]
            prop["default"] = field_def.default_factory()
        else:
            required.append(field_def.name)
        properties[field_def.name] = prop

    description = (op_cls.__doc__ or op_cls.name).strip().split("\n", maxsplit=1)[0]

    return {
        "name": to_tool_name(op_cls.name),
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def all_tool_specs(registry: dict[str, type[Op]] | None = None) -> list[dict[str, Any]]:
    """Return tool definitions for every Op in the registry, sorted by name."""
    table = registry if registry is not None else registered_ops()
    return [op_tool_spec(cls) for _, cls in sorted(table.items())]
