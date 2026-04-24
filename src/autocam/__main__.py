"""AutoCam entrypoint — delegates to the CLI."""

from __future__ import annotations

import sys

from autocam.cli import main

__all__ = ["main"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
