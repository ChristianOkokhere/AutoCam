"""Chat pane — scrollable message log + single-line input."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, RichLog


class ChatPane(Vertical):
    """Left pane: a scrollable log on top, an Input pinned to the bottom."""

    DEFAULT_CSS = """
    ChatPane {
        padding: 0 1;
    }
    ChatPane > RichLog {
        height: 1fr;
        background: $surface;
    }
    ChatPane > Input {
        dock: bottom;
        margin: 1 0 0 0;
    }
    """

    class Submitted(Message):
        """Posted whenever the user hits enter on the chat input."""

        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def compose(self) -> ComposeResult:
        yield RichLog(id="chat-log", wrap=True, markup=False, highlight=False)
        yield Input(placeholder=":add tone.exposure ev=0.3", id="chat-input")

    def write(self, line: str, *, role: str = "system") -> None:
        prefix = {"user": "> ", "system": "  ", "error": "! "}.get(role, "  ")
        self.query_one("#chat-log", RichLog).write(f"{prefix}{line}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        self.write(text, role="user")
        self.post_message(self.Submitted(text))

    def focus_input(self) -> None:
        self.query_one("#chat-input", Input).focus()
