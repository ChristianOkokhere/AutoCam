"""AutoCam CLI — Phase 1 supports ``apply``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autocam import BANNER
from autocam.io.image import save_image
from autocam.pipeline.executor import run_stack
from autocam.pipeline.stack import EditStack


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autocam", description="AutoCam CLI.")
    sub = parser.add_subparsers(dest="cmd")

    apply_p = sub.add_parser("apply", help="Apply an edit stack to an image.")
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
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        print(BANNER)
        print("Usage: autocam apply --stack <stack.json> --in <photo.jpg> --out <out.jpg>")
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
