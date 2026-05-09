"""Preview pane — renders the current pipeline output as an inline image."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static
from textual_image.widget import Image as ImageWidget

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage


class PreviewPane(Container):
    """Center pane: holds a status line and a single inline image widget."""

    DEFAULT_CSS = """
    PreviewPane {
        align: center middle;
        padding: 1;
    }
    PreviewPane > #preview-status {
        dock: top;
        color: $text-muted;
        height: 1;
    }
    PreviewPane > #preview-image {
        width: 1fr;
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("(no image — `:open <path>` to load one)", id="preview-status")
        yield ImageWidget(id="preview-image")

    def show_image(self, pil_image: PILImage, *, status: str = "") -> None:
        self.query_one("#preview-status", Static).update(status)
        self.query_one("#preview-image", ImageWidget).image = pil_image

    def clear(self) -> None:
        self.query_one("#preview-status", Static).update("(no image — `:open <path>` to load one)")
        self.query_one("#preview-image", ImageWidget).image = None
