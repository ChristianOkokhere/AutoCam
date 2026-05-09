"""History pane — renders the current edit stack as a numbered list."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from autocam.pipeline.stack import EditStack


class HistoryPane(VerticalScroll):
    """Right pane: live view of the edit stack."""

    DEFAULT_CSS = """
    HistoryPane {
        padding: 1;
    }
    HistoryPane > #history-list {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("(empty)", id="history-list")

    def update_from(self, stack: EditStack) -> None:
        widget = self.query_one("#history-list", Static)
        if not stack.ops:
            widget.update("(empty)")
            return
        lines = [f"{i:2d}. {op.describe()}" for i, op in enumerate(stack.ops, 1)]
        widget.update("\n".join(lines))
