"""Thin wrapper around the Anthropic SDK.

The SDK reads ``ANTHROPIC_API_KEY`` from the environment when no explicit key
is passed. We pin specific model IDs so a swap is one constant change rather
than a hunt across the codebase, and we hand the system prompt back as a
cache-eligible content block list.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import anthropic

from autocam.llm.recipes import render_knowledge_block

DEFAULT_MODEL = "claude-sonnet-4-6"
DEEP_MODEL = "claude-opus-4-7"
MAX_TOKENS = 4096

_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"
_FEW_SHOT = """
# Worked example

User: "warm the highlights and lift the shadows a touch"

Assistant calls (in one turn):

  tone_shadows({"amount": 18})
  color_white_balance({"temp_shift": 8, "tint": 0})

After both tool_results return, the assistant replies:

  "Warmer top end, shadows opened a hair. Want more?"

Two decisive calls, one short reply, no recap of what the JSON did.
""".strip()


def load_system_prompt() -> str:
    """Read the bundled system prompt from ``llm/prompts/system.md``."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_full_system_text(
    *,
    base_prompt: str | None = None,
    knowledge: str | None = None,
    few_shot: str | None = None,
) -> str:
    """Assemble the full system text: base prompt + knowledge + worked example.

    Order is fixed so the prompt cache stays warm across runs.
    """
    base = base_prompt if base_prompt is not None else load_system_prompt()
    body = knowledge if knowledge is not None else render_knowledge_block()
    shot = few_shot if few_shot is not None else _FEW_SHOT
    return f"{base.rstrip()}\n\n{body.rstrip()}\n\n{shot.rstrip()}\n"


def system_blocks(text: str | None = None) -> list[dict[str, Any]]:
    """Return system content blocks with prompt caching enabled.

    By default this bundles the base prompt + the recipe library + the worked
    example into one cacheable block.
    """
    final = text if text is not None else build_full_system_text()
    return [
        {
            "type": "text",
            "text": final,
            "cache_control": {"type": "ephemeral"},
        }
    ]


class LLMClient:
    """Minimal facade over ``anthropic.Anthropic``.

    Tests pass a fake with the same shape; production passes nothing and the
    SDK reads the API key from the environment.
    """

    def __init__(self, *, api_key: str | None = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    def create(
        self,
        *,
        model: str,
        system: list[dict[str, Any]] | str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = MAX_TOKENS,
        tool_choice: dict[str, Any] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": messages,
            "tools": tools,
            "max_tokens": max_tokens,
        }
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        return self._client.messages.create(**kwargs)


def env_has_api_key() -> bool:
    """Quick guard the TUI uses before kicking off an LLM turn."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
