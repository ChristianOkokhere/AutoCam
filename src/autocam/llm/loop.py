"""Vision + tool-use loop.

Each user turn:

1. Render the current preview, send it as a vision input alongside the stack
   JSON and the user's text.
2. Call Claude with the full tool surface and ``tool_choice: auto``.
3. For each ``tool_use`` block, look up the op, append it to the stack, and
   regenerate the preview. Tool results carry a histogram summary so the model
   can self-correct without re-seeing the image.
4. Loop until the model returns ``stop_reason != "tool_use"`` or we hit
   ``MAX_TURNS``.

The loop talks to the outside world through ``on_event`` callbacks so the TUI
can stream text into the chat pane and update the history pane as ops land.
"""

from __future__ import annotations

import base64
import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt
from PIL import Image as PILImage

from autocam.llm.client import DEFAULT_MODEL, system_blocks
from autocam.llm.tools import all_tool_specs, from_tool_name
from autocam.ops import registered_ops
from autocam.pipeline.color import linear_to_srgb
from autocam.pipeline.stack import EditStack

Float32Array = npt.NDArray[np.float32]

PREVIEW_LONG_EDGE = 1024
MAX_TURNS = 8


@dataclass
class TextEvent:
    text: str


@dataclass
class ToolEvent:
    op_name: str
    params: dict[str, Any]


@dataclass
class ErrorEvent:
    message: str


@dataclass
class StopEvent:
    reason: str


Event = TextEvent | ToolEvent | ErrorEvent | StopEvent


class _ClientLike(Protocol):
    def create(
        self,
        *,
        model: str,
        system: list[dict[str, Any]] | str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = ...,
        tool_choice: dict[str, Any] | None = ...,
    ) -> Any: ...


def encode_preview_png(arr: Float32Array, *, max_edge: int = PREVIEW_LONG_EDGE) -> str:
    """Encode a linear-sRGB float32 image as a base64 PNG."""
    display = linear_to_srgb(arr)
    arr8 = np.clip(display * 255.0, 0, 255).astype(np.uint8)
    pil = PILImage.fromarray(arr8)
    if max(pil.size) > max_edge:
        pil.thumbnail((max_edge, max_edge), PILImage.LANCZOS)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def histogram_summary(arr: Float32Array) -> dict[str, list[float]]:
    """Per-channel mean / p05 / p50 / p95 in display sRGB, rounded to 4 dp."""
    display = linear_to_srgb(arr)
    return {
        "mean": [round(float(display[..., c].mean()), 4) for c in range(3)],
        "p05": [round(float(np.percentile(display[..., c], 5)), 4) for c in range(3)],
        "p50": [round(float(np.percentile(display[..., c], 50)), 4) for c in range(3)],
        "p95": [round(float(np.percentile(display[..., c], 95)), 4) for c in range(3)],
    }


def build_user_content(
    *, stack: EditStack, user_text: str, preview_b64: str
) -> list[dict[str, Any]]:
    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": preview_b64,
            },
        },
        {
            "type": "text",
            "text": (
                f"current edit stack (read-only context):\n```json\n{stack.to_json(indent=2)}\n```"
            ),
        },
        {"type": "text", "text": user_text},
    ]


@dataclass
class _Block:
    """Normalised view of an SDK content block."""

    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)


def _normalise(block: Any) -> _Block:
    """Accept either an SDK pydantic block or a plain dict and return a _Block."""
    if isinstance(block, dict):
        return _Block(
            type=block.get("type", ""),
            text=block.get("text", ""),
            id=block.get("id", ""),
            name=block.get("name", ""),
            input=dict(block.get("input") or {}),
        )
    return _Block(
        type=getattr(block, "type", ""),
        text=getattr(block, "text", "") or "",
        id=getattr(block, "id", "") or "",
        name=getattr(block, "name", "") or "",
        input=dict(getattr(block, "input", {}) or {}),
    )


def _serialise_assistant_content(blocks: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in blocks:
        b = _normalise(raw)
        if b.type == "text":
            out.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            out.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return out


def _tool_error(tool_use_id: str, msg: str) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "is_error": True,
        "content": json.dumps({"ok": False, "error": msg}),
    }


def _tool_ok(
    tool_use_id: str,
    summary: dict[str, list[float]],
    *,
    op_id: str = "",
    op_name: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "summary": summary}
    if op_id:
        payload["op_id"] = op_id
    if op_name:
        payload["op_name"] = op_name
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": json.dumps(payload),
    }


def run_turn(
    *,
    client: _ClientLike,
    stack: EditStack,
    user_text: str,
    refresh_preview: Callable[[EditStack], Float32Array],
    model: str = DEFAULT_MODEL,
    system: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    on_event: Callable[[Event], None] | None = None,
    max_turns: int = MAX_TURNS,
) -> EditStack:
    """Drive one user turn end-to-end, mutating ``stack``.

    Pass ``tool_choice={"type": "none"}`` to forbid tool calls — the loop
    becomes a single round-trip and ``stack`` is left untouched.
    """
    if system is None:
        system = system_blocks()
    if tools is None:
        tools = all_tool_specs()
    emit = on_event if on_event is not None else (lambda _e: None)

    preview_b64 = encode_preview_png(refresh_preview(stack))
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": build_user_content(
                stack=stack, user_text=user_text, preview_b64=preview_b64
            ),
        }
    ]

    for _ in range(max_turns):
        response = client.create(
            model=model,
            system=system,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
        blocks = [_normalise(b) for b in response.content]

        for block in blocks:
            if block.type == "text" and block.text:
                emit(TextEvent(text=block.text))

        messages.append(
            {"role": "assistant", "content": _serialise_assistant_content(response.content)}
        )

        stop_reason = getattr(response, "stop_reason", None) or "end_turn"
        if stop_reason != "tool_use":
            emit(StopEvent(reason=str(stop_reason)))
            return stack

        tool_results: list[dict[str, Any]] = []
        registry = registered_ops()
        for block in blocks:
            if block.type != "tool_use":
                continue
            try:
                op_name = from_tool_name(block.name, registry=registry)
            except KeyError:
                emit(ErrorEvent(message=f"unknown tool: {block.name!r}"))
                tool_results.append(_tool_error(block.id, f"unknown tool: {block.name!r}"))
                continue

            op_cls = registry[op_name]
            try:
                op = op_cls(**block.input)
            except TypeError as exc:
                emit(ErrorEvent(message=f"{op_name}: bad params: {exc}"))
                tool_results.append(_tool_error(block.id, f"bad params: {exc}"))
                continue

            stack.append(op)
            emit(ToolEvent(op_name=op_name, params=dict(block.input)))

            try:
                arr = refresh_preview(stack)
                summary = histogram_summary(arr)
            except (OSError, ValueError, KeyError) as exc:
                stack.pop()
                emit(ErrorEvent(message=f"{op_name} failed: {exc}"))
                tool_results.append(_tool_error(block.id, f"pipeline error: {exc}"))
                continue

            tool_results.append(_tool_ok(block.id, summary, op_id=op.id, op_name=op_name))

        messages.append({"role": "user", "content": tool_results})

    emit(StopEvent(reason="max_turns"))
    return stack
