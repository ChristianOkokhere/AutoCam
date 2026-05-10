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
from autocam.ops import MaskOp
from autocam.pipeline.batch import (
    DEFAULT_TEMPLATE,
    BatchResult,
    expand_inputs,
    run_many,
)
from autocam.pipeline.color import linear_to_srgb
from autocam.pipeline.executor import run_stack, run_stack_with_ctx
from autocam.pipeline.presets import default_export_path, export_with_preset, get_preset
from autocam.pipeline.stack import EditStack, source_hash
from autocam.tui.commands import (
    AddCommand,
    BatchApplyCommand,
    ChatMessage,
    CommandError,
    CritiqueCommand,
    ExportCommand,
    HelpCommand,
    MaskHideCommand,
    MaskShowCommand,
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
        Binding("ctrl+question_mark", "help", "Help", priority=True),
    ]

    def __init__(self, image_path: Path | None = None) -> None:
        super().__init__()
        self.stack: EditStack = EditStack(source="")
        self._undo: list[Op] = []
        self._llm_busy: bool = False
        self._mask_overlay: str | None = None
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
        if isinstance(cmd, MaskShowCommand):
            self._handle_mask_show(cmd)
            return
        if isinstance(cmd, MaskHideCommand):
            self._handle_mask_hide()
            return
        if isinstance(cmd, BatchApplyCommand):
            self._handle_batch_apply(cmd)
            return
        if isinstance(cmd, ExportCommand):
            self._handle_export(cmd)
            return
        if isinstance(cmd, HelpCommand):
            self.action_help()
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
            arr, ctx = run_stack_with_ctx(self.stack, preview=True)
        except (OSError, ValueError, KeyError) as exc:
            self.query_one(ChatPane).write(f"preview failed: {exc}", role="error")
            return

        display = linear_to_srgb(arr)
        if self._mask_overlay and self._mask_overlay in ctx.masks:
            display = _composite_mask_overlay(display, ctx.masks[self._mask_overlay])

        arr8 = np.clip(display * 255.0, 0, 255).astype(np.uint8)
        pil = PILImage.fromarray(arr8)
        suffix = f"  · mask:{self._mask_overlay[:6]}" if self._mask_overlay else ""
        preview.show_image(
            pil,
            status=f"{Path(self.stack.source).name}  {pil.width}x{pil.height}{suffix}",
        )

    # ── mask overlay ──────────────────────────────────────────────────

    def _handle_mask_show(self, cmd: MaskShowCommand) -> None:
        chat = self.query_one(ChatPane)
        if not self.stack.source:
            chat.write("no image loaded — `:open <path>` first", role="error")
            return
        target_id = self._resolve_mask_target(cmd.target)
        if target_id is None:
            chat.write(f":mask show: no mask matches {cmd.target!r}", role="error")
            return
        self._mask_overlay = target_id
        chat.write(f"mask overlay → {target_id[:6]}…")
        self._refresh_preview()

    def _handle_mask_hide(self) -> None:
        chat = self.query_one(ChatPane)
        if self._mask_overlay is None:
            chat.write("no mask overlay active", role="error")
            return
        self._mask_overlay = None
        chat.write("mask overlay cleared")
        self._refresh_preview()

    def _resolve_mask_target(self, target: str) -> str | None:
        """Find a mask op id by full id, prefix, or `last`/empty."""
        mask_ops = [op for op in self.stack.ops if isinstance(op, MaskOp)]
        if not mask_ops:
            return None
        if target in {"", "last"}:
            return mask_ops[-1].id
        for op in mask_ops:
            if op.id == target or op.id.startswith(target):
                return op.id
        return None

    # ── batch ─────────────────────────────────────────────────────────

    def _handle_batch_apply(self, cmd: BatchApplyCommand) -> None:
        chat = self.query_one(ChatPane)
        if not cmd.stack_path.exists():
            chat.write(f":batch apply: stack file not found: {cmd.stack_path}", role="error")
            return
        sources = expand_inputs([cmd.glob])
        if not sources:
            chat.write(f":batch apply: no files matched {cmd.glob!r}", role="error")
            return
        out_template = cmd.out_template or DEFAULT_TEMPLATE
        chat.write(f"batch: {len(sources)} file(s), template={out_template!r}")

        def emit(r: BatchResult) -> None:
            self.call_from_thread(self._batch_event, r)

        def work() -> None:
            run_many(
                stack_path=cmd.stack_path,
                sources=sources,
                out_template=out_template,
                workers=1,  # in-process inside the TUI to keep state simple
                on_event=emit,
            )
            self.call_from_thread(chat.write, "batch: done.")

        self.run_worker(work, thread=True, exclusive=True, group="batch")

    def _batch_event(self, r: BatchResult) -> None:
        chat = self.query_one(ChatPane)
        if r.ok and r.output is not None:
            chat.write(
                f"[{r.idx}/{r.total}] {r.source.name} -> {r.output.name}  ({r.seconds:.1f}s)"
            )
        else:
            chat.write(
                f"[{r.idx}/{r.total}] {r.source.name} FAILED: {r.error}",
                role="error",
            )

    # ── export presets ────────────────────────────────────────────────

    def _handle_export(self, cmd: ExportCommand) -> None:
        chat = self.query_one(ChatPane)
        if not self.stack.source:
            chat.write("no image loaded — `:open <path>` first", role="error")
            return
        try:
            preset = get_preset(cmd.preset)
        except KeyError as exc:
            chat.write(str(exc), role="error")
            return
        out_path = cmd.out_path or default_export_path(self.stack.source, preset.name)
        chat.write(f"exporting {preset.name} → {out_path}…")

        def work() -> None:
            try:
                final = export_with_preset(
                    stack=self.stack,
                    preset=preset.name,
                    out_path=out_path,
                )
            except (OSError, ValueError, KeyError) as exc:
                self.call_from_thread(chat.write, f"export failed: {exc}", role="error")
                return
            self.call_from_thread(chat.write, f"wrote {final}")

        self.run_worker(work, thread=True, exclusive=True, group="export")

    # ── help overlay ──────────────────────────────────────────────────

    def action_help(self) -> None:
        chat = self.query_one(ChatPane)
        for line in _HELP_TEXT.splitlines():
            chat.write(line)


_HELP_TEXT = """\
AutoCam command reference
─────────────────────────
Chat (anything not starting with `:` or `/`)  → Claude vision + tool-use loop
/deep <message>      use Claude Opus 4.7 for one turn
/critique [text]     read-only photo critique (stack untouched)

:open <path>         load a JPEG / PNG / TIFF / RAW
:add <op> [k=v...]   manually append an op (see :help ops)
:undo                drop the last op (Ctrl+Z)
:redo                replay it          (Ctrl+Y)
:mask show [target]  overlay a mask  (target = id, prefix, or `last`)
:mask hide           clear the overlay
:batch apply <stack> <glob> [<template>]   apply a saved stack to many files
:export <preset>     save (preset = web / print). Default path:
                       <name>_<preset>.jpg next to the source.
:help                show this reference  (?)
:quit                exit

Examples
────────
warm the highlights and lift the shadows a touch
darken just the sky
give this a teal-and-orange cinematic look
:add tone.exposure ev=0.3
:add struct.border width_pct=2 color=#ffffff
:export web
"""


def _composite_mask_overlay(display: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Tint the preview magenta where ``mask`` is non-zero."""
    if mask.shape != display.shape[:2]:
        return display
    alpha = (mask * 0.5).clip(0.0, 0.5).astype(np.float32)[..., None]
    magenta = np.array([1.0, 0.15, 0.85], dtype=np.float32)
    return (display * (1.0 - alpha) + magenta * alpha).astype(np.float32)


def run(image_path: Path | None = None) -> None:
    """Launch the TUI. Used by the `create` CLI."""
    AutoCamApp(image_path=image_path).run()
