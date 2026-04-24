"""AutoCam entrypoint — Phase 0 placeholder."""

from __future__ import annotations

import sys

from autocam import __version__

BANNER = f"""
  ┌──────────────────────────────────────────────┐
  │  AutoCam  v{__version__:<8}                          │
  │  Natural-language RAW photo editor.          │
  │  Pre-alpha · see PLAN.md for the roadmap.    │
  └──────────────────────────────────────────────┘
"""


def main(argv: list[str] | None = None) -> int:
    del argv  # Phase 0: no args parsed yet.
    print(BANNER)
    print("Phase 0 scaffolding active. No edit pipeline yet — see PLAN.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
