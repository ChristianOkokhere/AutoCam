"""AutoCam CLI.

* ``create``                      → launches the TUI (no image loaded)
* ``create path/to/photo.jpg``   → launches the TUI with that photo loaded
* ``create apply --stack ...``   → one-shot batch mode (Phase 1)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autocam import BANNER
from autocam.io.image import save_image
from autocam.pipeline.executor import run_stack
from autocam.pipeline.stack import EditStack

_SUBCOMMANDS = {"apply"}


def _apply(args: argparse.Namespace) -> int:
    stack = EditStack.load(args.stack)
    source = args.input if args.input is not None else Path(stack.source)
    img = run_stack(stack, source=source, preview=args.preview)

    fmt = args.format
    if fmt is None:
        fmt = args.out.suffix.lstrip(".").lower() or "jpeg"
    if fmt == "jpg":
        fmt = "jpeg"

    save_image(img, args.out, format=fmt, quality=args.quality)
    print(f"wrote {args.out}")
    return 0


def _launch_tui(image_path: Path | None) -> int:
    # Imported lazily so `create apply ...` doesn't pay the Textual import cost.
    from autocam.tui.screen import run as run_tui

    run_tui(image_path=image_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create",
        description="AutoCam — natural-language photo editor in your terminal.",
    )
    sub = parser.add_subparsers(dest="cmd")

    apply_p = sub.add_parser("apply", help="Apply an edit stack to an image (no TUI).")
    apply_p.add_argument("--stack", type=Path, required=True, help="Path to edit stack JSON.")
    apply_p.add_argument(
        "--in",
        dest="input",
        type=Path,
        default=None,
        help="Source image path (overrides stack.source).",
    )
    apply_p.add_argument("--out", type=Path, required=True, help="Output image path.")
    apply_p.add_argument(
        "--format",
        type=str,
        default=None,
        help="Output format: jpeg/png/tiff (default: inferred from --out extension).",
    )
    apply_p.add_argument("--quality", type=int, default=90)
    apply_p.add_argument(
        "--preview",
        action="store_true",
        help="Downscale to preview size before applying ops.",
    )
    apply_p.set_defaults(func=_apply)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)

    if args and args[0] in {"-h", "--help"}:
        build_parser().parse_args(args)
        return 0
    if args and args[0] == "--version":
        from autocam import __version__

        print(__version__)
        return 0

    if not args:
        return _launch_tui(image_path=None)

    if args[0] not in _SUBCOMMANDS and not args[0].startswith("-"):
        # Treat as `create <image_path>`.
        path = Path(args[0]).expanduser()
        if not path.exists():
            print(BANNER)
            print(f"error: no such file: {path}", file=sys.stderr)
            return 2
        return _launch_tui(image_path=path)

    parsed = build_parser().parse_args(args)
    if not hasattr(parsed, "func"):
        return _launch_tui(image_path=None)
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
