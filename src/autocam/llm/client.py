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

DEFAULT_MODEL = "claude-sonnet-4-6"
DEEP_MODEL = "claude-opus-4-7"
MAX_TOKENS = 4096

_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


def load_system_prompt() -> str:
    """Read the bundled system prompt from ``llm/prompts/system.md``."""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def system_blocks(text: str | None = None) -> list[dict[str, Any]]:
    """Return system content blocks with prompt caching enabled."""
    return [
        {
            "type": "text",
            "text": text if text is not None else load_system_prompt(),
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
    ) -> Any:
        return self._client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
        )


def env_has_api_key() -> bool:
    """Quick guard the TUI uses before kicking off an LLM turn."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
