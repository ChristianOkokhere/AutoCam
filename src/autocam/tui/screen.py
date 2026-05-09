"""AutoCam Textual app — three-pane editor screen.

Layout::

    ┌── Header ────────────────────────────────────────────┐
    │ Chat (1fr)  │  Preview (2fr)        │ History (1fr) │
    └── Footer ────────────────────────────────────────────┘

Phase 2 wires manual op insertion via colon commands. The chat is just an
echo loop today; Phase 3 swaps in the Claude tool-use loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from PIL import Image as PILImage
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from autocam.pipeline.color import linear_to_srgb
from autocam.pipeline.executor import run_stack
from autocam.pipeline.stack import EditStack, source_hash
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
from autocam.tui.widgets.chat import ChatPane
from autocam.tui.widgets.history import HistoryPane
from autocam.tui.widgets.preview import PreviewPane

if TYPE_CHECKING:
    from autocam.ops import Op


class AutoCamApp(App[None]):
    """Three-pane TUI: chat | preview | history."""

    TITLE = "AutoCam"
    SUB_TITLE = "natural-language photo editor"

    CSS = """
    Horizontal#main {
        height: 1fr;
    }
    ChatPane {
        width: 1fr;
        border-right: solid $accent;
    }
    PreviewPane {
        width: 2fr;
    }
    HistoryPane {
        width: 1fr;
        border-left: solid $accent;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+z", "undo", "Undo", priority=True),
        Binding("ctrl+y", "redo", "Redo", priority=True),
    ]

    def __init__(self, image_path: Path | None = None) -> None:
        super().__init__()
        self.stack: EditStack = EditStack(source="")
        self._undo: list[Op] = []
        self._pending_source: Path | None = (
            Path(image_path).expanduser().resolve() if image_path else None
        )

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield ChatPane(id="chat")
            yield PreviewPane(id="preview")
            yield HistoryPane(id="history")
        yield Footer()

    def on_mount(self) -> None:
        chat = self.query_one(ChatPane)
        if self._pending_source is not None:
            try:
                self._set_source(self._pending_source)
            except (OSError, ValueError) as exc:
                chat.write(f"open failed: {exc}", role="error")
            else:
                chat.write(f"loaded {self.stack.source}")
                self._refresh_preview()
        else:
            chat.write("Welcome to AutoCam.")
            chat.write("Use `:open <path>`, `:add <op> k=v`, `:undo`, `:redo`, `:quit`.")
        self.query_one(HistoryPane).update_from(self.stack)
        chat.focus_input()

    # ── command dispatch ──────────────────────────────────────────────

    def on_chat_pane_submitted(self, event: ChatPane.Submitted) -> None:
        chat = self.query_one(ChatPane)
        try:
            cmd = parse_command(event.text)
        except CommandError as exc:
            chat.write(str(exc), role="error")
            return

        if isinstance(cmd, ChatMessage):
            chat.write(
                "LLM not yet wired (Phase 3). Use :add / :undo / :redo / :open / :quit.",
                role="system",
            )
            return
        if isinstance(cmd, OpenCommand):
            self._handle_open(cmd.path)
            return
        if isinstance(cmd, AddCommand):
            self._handle_add(cmd)
            return
        if isinstance(cmd, UndoCommand):
            self.action_undo()
            return
        if isinstance(cmd, RedoCommand):
            self.action_redo()
            return
        if isinstance(cmd, QuitCommand):
            self.exit()
            return

    def _handle_open(self, path: Path) -> None:
        chat = self.query_one(ChatPane)
        try:
            self._set_source(path)
        except (OSError, ValueError) as exc:
            chat.write(f"open failed: {exc}", role="error")
            return
        chat.write(f"loaded {self.stack.source}")
        self.query_one(HistoryPane).update_from(self.stack)
        self._refresh_preview()

    def _handle_add(self, cmd: AddCommand) -> None:
        chat = self.query_one(ChatPane)
        if not self.stack.source:
            chat.write("no image loaded — `:open <path>` first", role="error")
            return
        try:
            op = build_op(cmd.op_name, cmd.raw_params)
        except (CommandError, KeyError, ValueError, TypeError) as exc:
            chat.write(f"add failed: {exc}", role="error")
            return
        self.stack.append(op)
        self._undo.clear()
        chat.write(f"+ {op.describe()}")
        self.query_one(HistoryPane).update_from(self.stack)
        self._refresh_preview()

    # ── undo / redo ───────────────────────────────────────────────────

    def action_undo(self) -> None:
        chat = self.query_one(ChatPane)
        if not self.stack.ops:
            chat.write("nothing to undo", role="error")
            return
        op = self.stack.pop()
        self._undo.append(op)
        chat.write(f"- {op.describe()}")
        self.query_one(HistoryPane).update_from(self.stack)
        self._refresh_preview()

    def action_redo(self) -> None:
        chat = self.query_one(ChatPane)
        if not self._undo:
            chat.write("nothing to redo", role="error")
            return
        op = self._undo.pop()
        self.stack.append(op)
        chat.write(f"+ {op.describe()}")
        self.query_one(HistoryPane).update_from(self.stack)
        self._refresh_preview()

    # ── pipeline glue ─────────────────────────────────────────────────

    def _set_source(self, path: Path) -> None:
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"no such file: {resolved}")
        self.stack = EditStack(source=str(resolved), source_hash=source_hash(resolved))
        self._undo.clear()

    def _refresh_preview(self) -> None:
        if not self.stack.source:
            return
        preview = self.query_one(PreviewPane)
        try:
            arr = run_stack(self.stack, preview=True)
        except (OSError, ValueError) as exc:
            self.query_one(ChatPane).write(f"preview failed: {exc}", role="error")
            return
        display = linear_to_srgb(arr)
        arr8 = np.clip(display * 255.0, 0, 255).astype(np.uint8)
        pil = PILImage.fromarray(arr8)
        preview.show_image(
            pil,
            status=f"{Path(self.stack.source).name}  {pil.width}x{pil.height}",
        )


def run(image_path: Path | None = None) -> None:
    """Launch the TUI. Used by the `create` CLI."""
    AutoCamApp(image_path=image_path).run()
