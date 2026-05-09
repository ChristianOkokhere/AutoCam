"""End-to-end tests for the LLM loop, using a fake Anthropic client."""

from __future__ import annotations

import base64
import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from autocam.io.image import load_image
from autocam.llm.loop import (
    ErrorEvent,
    StopEvent,
    TextEvent,
    ToolEvent,
    encode_preview_png,
    histogram_summary,
    run_turn,
)
from autocam.pipeline.executor import run_stack
from autocam.pipeline.stack import EditStack


@dataclass
class FakeBlock:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeResponse:
    content: list[FakeBlock]
    stop_reason: str = "end_turn"


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        # Deep-copy `messages` so later mutations by the loop don't bleed
        # back into earlier captured calls.
        snapshot = dict(kwargs)
        snapshot["messages"] = copy.deepcopy(kwargs["messages"])
        self.calls.append(snapshot)
        return self.responses.pop(0)


def _refresh(stack: EditStack) -> np.ndarray:
    return run_stack(stack, preview=True)


def test_encode_preview_png_returns_base64() -> None:
    img = np.full((128, 256, 3), 0.5, dtype=np.float32)
    encoded = encode_preview_png(img, max_edge=64)
    raw = base64.b64decode(encoded)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


def test_histogram_summary_shape() -> None:
    img = np.linspace(0, 1, 256 * 3, dtype=np.float32).reshape(16, 16, 3)
    summary = histogram_summary(img)
    assert set(summary) == {"mean", "p05", "p50", "p95"}
    for key in summary:
        assert len(summary[key]) == 3


def test_run_turn_executes_one_tool_then_stops(fixture_jpeg: Path) -> None:
    stack = EditStack(source=str(fixture_jpeg))
    fake = FakeClient(
        [
            FakeResponse(
                content=[
                    FakeBlock(type="text", text="Bumping exposure."),
                    FakeBlock(
                        type="tool_use",
                        id="t1",
                        name="tone_exposure",
                        input={"ev": 0.5},
                    ),
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(
                content=[FakeBlock(type="text", text="Done.")],
                stop_reason="end_turn",
            ),
        ]
    )
    events: list[Any] = []
    run_turn(
        client=fake,
        stack=stack,
        user_text="bump exposure a bit",
        refresh_preview=_refresh,
        on_event=events.append,
    )
    assert len(stack.ops) == 1
    assert stack.ops[0].name == "tone.exposure"
    assert any(isinstance(e, TextEvent) and "Bumping" in e.text for e in events)
    assert any(isinstance(e, ToolEvent) and e.op_name == "tone.exposure" for e in events)
    assert any(isinstance(e, StopEvent) and e.reason == "end_turn" for e in events)


def test_run_turn_chains_two_tools_in_one_response(fixture_jpeg: Path) -> None:
    stack = EditStack(source=str(fixture_jpeg))
    fake = FakeClient(
        [
            FakeResponse(
                content=[
                    FakeBlock(type="tool_use", id="a", name="tone_shadows", input={"amount": 25}),
                    FakeBlock(
                        type="tool_use",
                        id="b",
                        name="color_white_balance",
                        input={"temp_shift": 200, "tint": 0},
                    ),
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[FakeBlock(type="text", text="ok")], stop_reason="end_turn"),
        ]
    )
    run_turn(
        client=fake,
        stack=stack,
        user_text="warm and lift shadows",
        refresh_preview=_refresh,
    )
    op_names = [op.name for op in stack.ops]
    assert op_names == ["tone.shadows", "color.white_balance"]


def test_run_turn_unknown_tool_reports_error(fixture_jpeg: Path) -> None:
    stack = EditStack(source=str(fixture_jpeg))
    fake = FakeClient(
        [
            FakeResponse(
                content=[
                    FakeBlock(type="tool_use", id="x", name="not_a_tool", input={}),
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[FakeBlock(type="text", text="ok")], stop_reason="end_turn"),
        ]
    )
    events: list[Any] = []
    run_turn(
        client=fake,
        stack=stack,
        user_text="do nothing useful",
        refresh_preview=_refresh,
        on_event=events.append,
    )
    assert stack.ops == []
    assert any(isinstance(e, ErrorEvent) and "unknown tool" in e.message for e in events)
    # The fake's *second* call should carry an is_error tool_result.
    second_call = fake.calls[1]
    second_user_msg = second_call["messages"][-1]
    assert second_user_msg["role"] == "user"
    payload = second_user_msg["content"][0]
    assert payload["is_error"] is True
    assert json.loads(payload["content"])["ok"] is False


def test_run_turn_bad_params_rolls_back(fixture_jpeg: Path) -> None:
    stack = EditStack(source=str(fixture_jpeg))
    fake = FakeClient(
        [
            FakeResponse(
                content=[
                    FakeBlock(
                        type="tool_use",
                        id="bad",
                        name="tone_exposure",
                        input={"nope": 1.0},
                    ),
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(content=[FakeBlock(type="text", text="ok")], stop_reason="end_turn"),
        ]
    )
    events: list[Any] = []
    run_turn(
        client=fake,
        stack=stack,
        user_text="trip me up",
        refresh_preview=_refresh,
        on_event=events.append,
    )
    assert stack.ops == []
    assert any(isinstance(e, ErrorEvent) for e in events)


def test_run_turn_max_turns_guard(fixture_jpeg: Path) -> None:
    stack = EditStack(source=str(fixture_jpeg))
    # The fake keeps returning tool_use forever; max_turns must stop the loop.
    looper = FakeResponse(
        content=[
            FakeBlock(type="tool_use", id="x", name="tone_exposure", input={"ev": 0.05}),
        ],
        stop_reason="tool_use",
    )
    fake = FakeClient([looper for _ in range(10)])
    events: list[Any] = []
    run_turn(
        client=fake,
        stack=stack,
        user_text="loop forever",
        refresh_preview=_refresh,
        on_event=events.append,
        max_turns=3,
    )
    assert any(isinstance(e, StopEvent) and e.reason == "max_turns" for e in events)
    assert len(stack.ops) == 3


def test_run_turn_first_message_carries_image(fixture_jpeg: Path) -> None:
    stack = EditStack(source=str(fixture_jpeg))
    fake = FakeClient(
        [FakeResponse(content=[FakeBlock(type="text", text="ok")], stop_reason="end_turn")]
    )
    run_turn(
        client=fake,
        stack=stack,
        user_text="hi",
        refresh_preview=_refresh,
    )
    first_call = fake.calls[0]
    user_content = first_call["messages"][0]["content"]
    types = [c["type"] for c in user_content]
    assert types[0] == "image"
    assert any(c["type"] == "text" and "edit stack" in c["text"] for c in user_content)
    assert any(c["type"] == "text" and c["text"] == "hi" for c in user_content)


def test_run_turn_passes_through_tool_choice_auto(fixture_jpeg: Path) -> None:
    """We don't set tool_choice today (SDK default == auto), but tools must be passed."""
    stack = EditStack(source=str(fixture_jpeg))
    fake = FakeClient(
        [FakeResponse(content=[FakeBlock(type="text", text="ok")], stop_reason="end_turn")]
    )
    run_turn(client=fake, stack=stack, user_text="hi", refresh_preview=_refresh)
    tools = fake.calls[0]["tools"]
    names = {t["name"] for t in tools}
    assert "tone_exposure" in names
    assert "color_white_balance" in names


@pytest.fixture
def loaded_array(fixture_jpeg: Path) -> np.ndarray:
    return load_image(fixture_jpeg)
