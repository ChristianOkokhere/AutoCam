"""AutoCam Textual app — three-pane editor screen.

Layout::

    ┌── Header ────────────────────────────────────────────┐
    │ Chat (1fr)  │  Preview (2fr)        │ History (1fr) │
    └── Footer ────────────────────────────────────────────┘

Phase 3 wires the Claude tool-use loop into the chat pane: any non-``:``
input is treated as natural language and runs through ``llm.loop.run_turn``.
``/deep <message>`` escalates that single turn to Claude Opus.
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
from textual.worker import Worker

from autocam.llm.client import DEEP_MODEL, DEFAULT_MODEL, LLMClient, env_has_api_key
from autocam.llm.loop import (
    ErrorEvent,
    Event,
    StopEvent,
    TextEvent,
    ToolEvent,
    run_turn,
)
from autocam.pipeline.color import linear_to_srgb
from autocam.pipeline.executor import run_stack
from autocam.pipeline.stack import EditStack, source_hash
from autocam.tui.commands import (
    AddCommand,
    ChatMessage,
    CommandError,
    CritiqueCommand,
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
        self._llm_busy: bool = False
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
            chat.write("`:open <path>` to load a photo, then describe edits in plain English.")
            chat.write("Manual ops: `:add <op> k=v`, `:undo`, `:redo`. `/deep <msg>` uses Opus.")
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
            self._handle_chat(cmd)
            return
        if isinstance(cmd, CritiqueCommand):
            self._handle_critique(cmd)
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

    # ── LLM chat ──────────────────────────────────────────────────────

    def _handle_chat(self, cmd: ChatMessage) -> None:
        chat = self.query_one(ChatPane)
        if not self._llm_preconditions_ok(chat):
            return
        model = DEEP_MODEL if cmd.deep else DEFAULT_MODEL
        self._llm_busy = True
        self._run_llm_turn(cmd.text, model=model, tool_choice=None)

    def _handle_critique(self, cmd: CritiqueCommand) -> None:
        chat = self.query_one(ChatPane)
        if not self._llm_preconditions_ok(chat):
            return
        prompt = cmd.text or "Critique this photograph. What's working, what isn't?"
        chat.write("(critique mode — Claude reads only)")
        self._llm_busy = True
        self._run_llm_turn(prompt, model=DEFAULT_MODEL, tool_choice={"type": "none"})

    def _llm_preconditions_ok(self, chat: ChatPane) -> bool:
        if not self.stack.source:
            chat.write("no image loaded — `:open <path>` first", role="error")
            return False
        if not env_has_api_key():
            chat.write(
                "ANTHROPIC_API_KEY not set — export it before chatting.",
                role="error",
            )
            return False
        if self._llm_busy:
            chat.write("a turn is already in flight — wait for it to finish", role="error")
            return False
        return True

    def _llm_emit(self, event: Event) -> None:
        """Translate loop events to UI updates. Runs on the UI thread."""
        chat = self.query_one(ChatPane)
        if isinstance(event, TextEvent):
            chat.write(event.text)
        elif isinstance(event, ToolEvent):
            chat.write(f"+ tool {event.op_name}({event.params})")
            self._undo.clear()
            self.query_one(HistoryPane).update_from(self.stack)
        elif isinstance(event, ErrorEvent):
            chat.write(event.message, role="error")
        elif isinstance(event, StopEvent):
            self._llm_busy = False

    def _llm_show_preview(self, arr: np.ndarray) -> None:
        """Push a freshly rendered array into the preview pane."""
        display = linear_to_srgb(arr.astype(np.float32))
        arr8 = np.clip(display * 255.0, 0, 255).astype(np.uint8)
        pil = PILImage.fromarray(arr8)
        preview = self.query_one(PreviewPane)
        preview.show_image(
            pil,
            status=f"{Path(self.stack.source).name}  {pil.width}x{pil.height}",
        )

    def _run_llm_turn(
        self,
        user_text: str,
        *,
        model: str,
        tool_choice: dict | None,
    ) -> Worker[None]:
        client = LLMClient()

        def refresh(stack: EditStack) -> np.ndarray:
            arr = run_stack(stack, preview=True)
            self.call_from_thread(self._llm_show_preview, arr)
            return arr

        def emit(event: Event) -> None:
            self.call_from_thread(self._llm_emit, event)

        def work() -> None:
            try:
                run_turn(
                    client=client,
                    stack=self.stack,
                    user_text=user_text,
                    refresh_preview=refresh,
                    model=model,
                    tool_choice=tool_choice,
                    on_event=emit,
                )
            except Exception as exc:
                self.call_from_thread(
                    self.query_one(ChatPane).write,
                    f"LLM error: {exc}",
                    role="error",
                )
                self.call_from_thread(self._llm_emit, StopEvent(reason="error"))

        return self.run_worker(work, thread=True, exclusive=True, group="llm")

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
