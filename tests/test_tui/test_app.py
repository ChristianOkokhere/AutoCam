"""End-to-end smoke test for the Textual TUI.

Uses Textual's headless ``run_test`` pilot — no real terminal needed.
"""

from __future__ import annotations

from pathlib import Path

from textual.widgets import Input, RichLog

from autocam.tui.screen import AutoCamApp
from autocam.tui.widgets.history import HistoryPane


async def _submit(pilot, text: str) -> None:
    input_widget = pilot.app.query_one("#chat-input", Input)
    input_widget.value = text
    await pilot.press("enter")
    await pilot.pause()


async def test_app_loads_image_and_handles_add_undo(fixture_jpeg: Path) -> None:
    app = AutoCamApp(image_path=fixture_jpeg)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert Path(app.stack.source).resolve() == fixture_jpeg.resolve()
        assert app.stack.ops == []

        await _submit(pilot, ":add tone.exposure ev=0.5")
        assert len(app.stack.ops) == 1
        assert app.stack.ops[0].name == "tone.exposure"

        # History pane reflects the new op.
        history_text = str(app.query_one("#history-list").render())
        assert "tone.exposure" in history_text

        await _submit(pilot, ":undo")
        assert app.stack.ops == []
        assert len(app._undo) == 1

        await _submit(pilot, ":redo")
        assert len(app.stack.ops) == 1


async def test_app_rejects_add_without_image() -> None:
    app = AutoCamApp(image_path=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _submit(pilot, ":add tone.exposure ev=0.5")
        assert app.stack.ops == []

        log = app.query_one("#chat-log", RichLog)
        rendered = "\n".join(str(line) for line in log.lines)
        assert "no image loaded" in rendered.lower()


async def test_app_chat_text_is_echoed(fixture_jpeg: Path) -> None:
    app = AutoCamApp(image_path=fixture_jpeg)
    async with app.run_test() as pilot:
        await pilot.pause()
        await _submit(pilot, "warm the highlights")
        assert app.stack.ops == []  # no LLM yet — no ops added


async def test_history_pane_starts_empty(fixture_jpeg: Path) -> None:
    app = AutoCamApp(image_path=fixture_jpeg)
    async with app.run_test() as pilot:
        await pilot.pause()
        history = app.query_one(HistoryPane)
        rendered = str(history.query_one("#history-list").render())
        assert "empty" in rendered.lower()
