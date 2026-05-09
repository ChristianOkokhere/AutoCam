"""Tests for the thin Anthropic client wrapper."""

from __future__ import annotations

from autocam.llm.client import (
    DEEP_MODEL,
    DEFAULT_MODEL,
    env_has_api_key,
    load_system_prompt,
    system_blocks,
)


def test_default_models_pinned() -> None:
    assert DEFAULT_MODEL == "claude-sonnet-4-6"
    assert DEEP_MODEL == "claude-opus-4-7"


def test_load_system_prompt_non_empty() -> None:
    prompt = load_system_prompt()
    assert "AutoCam" in prompt
    assert "tool" in prompt.lower()


def test_system_blocks_caches_system() -> None:
    blocks = system_blocks("hello")
    assert blocks == [
        {
            "type": "text",
            "text": "hello",
            "cache_control": {"type": "ephemeral"},
        }
    ]


def test_env_has_api_key_reads_env(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert env_has_api_key() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert env_has_api_key() is True
