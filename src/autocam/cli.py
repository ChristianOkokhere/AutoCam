"""AutoCam CLI.

* ``create``                          → launches the TUI (no image loaded)
* ``create path/to/photo.jpg``       → launches the TUI with that photo loaded
* ``create apply --stack ...``       → one-shot single-image batch mode
* ``create batch --stack ... --in '*.arw' --out '{stem}.jpg'`` → multi-image batch
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autocam import BANNER
from autocam.io.image import save_image
from autocam.pipeline.batch import (
    DEFAULT_TEMPLATE,
    BatchResult,
    auto_workers,
    expand_inputs,
    run_many,
)
from autocam.pipeline.executor import run_stack
from autocam.pipeline.presets import (
    PRESETS,
    default_export_path,
    export_with_preset,
)
from autocam.pipeline.stack import EditStack

_SUBCOMMANDS = {"apply", "batch", "export"}


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


def _format_batch_line(r: BatchResult) -> str:
    pad = max(2, len(str(r.total)))
    counter = f"[{str(r.idx).zfill(pad)}/{r.total}]"
    if r.ok and r.output is not None:
        return f"{counter} {r.source.name} -> {r.output.name}  ({r.seconds:.1f}s)"
    return f"{counter} {r.source.name} FAILED: {r.error}"


def _batch(args: argparse.Namespace) -> int:
    sources = expand_inputs(args.inputs)
    if not sources:
        print("error: no input files matched", file=sys.stderr)
        return 2
    workers = args.workers if args.workers > 0 else auto_workers()
    fmt = args.format if args.format != "jpg" else "jpeg"

    def on_event(r: BatchResult) -> None:
        line = _format_batch_line(r)
        stream = sys.stdout if r.ok else sys.stderr
        print(line, file=stream, flush=True)

    results = run_many(
        stack_path=args.stack,
        sources=sources,
        out_template=args.out,
        workers=workers,
        image_format=fmt,
        quality=args.quality,
        on_event=on_event,
    )

    failures = [r for r in results if not r.ok]
    print(f"\n{len(results) - len(failures)}/{len(results)} succeeded.", flush=True)
    if failures:
        print(f"{len(failures)} failed:", file=sys.stderr)
        for r in failures:
            print(f"  {r.source.name}: {r.error}", file=sys.stderr)
        return 1
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

    batch_p = sub.add_parser(
        "batch",
        help="Apply an edit stack to a glob of images, in parallel.",
    )
    batch_p.add_argument("--stack", type=Path, required=True, help="Path to edit stack JSON.")
    batch_p.add_argument(
        "--in",
        dest="inputs",
        nargs="+",
        required=True,
        help="One or more paths or glob patterns (e.g. 'shoot/*.arw').",
    )
    batch_p.add_argument(
        "--out",
        type=str,
        default=DEFAULT_TEMPLATE,
        help=(
            "Output path or template. Tokens: {name} {stem} {ext} {idx} {idx0} "
            "{stack_id}. A bare directory implies the default template. "
            f"Default: {DEFAULT_TEMPLATE!r}."
        ),
    )
    batch_p.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Parallel processes. 0 = auto (CPU count, capped at 8).",
    )
    batch_p.add_argument("--format", type=str, default="jpeg", help="jpeg / png / tiff")
    batch_p.add_argument("--quality", type=int, default=90)
    batch_p.set_defaults(func=_batch)

    export_p = sub.add_parser(
        "export",
        help="Apply a stack and save through a preset (web / print).",
    )
    export_p.add_argument(
        "preset",
        choices=sorted(PRESETS),
        help="One of: " + ", ".join(sorted(PRESETS)),
    )
    export_p.add_argument("--stack", type=Path, required=True, help="Path to edit stack JSON.")
    export_p.add_argument(
        "--in",
        dest="input",
        type=Path,
        default=None,
        help="Source image path (overrides stack.source).",
    )
    export_p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path. Default: <source>_<preset>.jpg next to the source.",
    )
    export_p.set_defaults(func=_export)

    return parser


def _export(args: argparse.Namespace) -> int:
    stack = EditStack.load(args.stack)
    source = args.input if args.input is not None else Path(stack.source)
    out = args.out if args.out is not None else default_export_path(source, args.preset)
    final = export_with_preset(stack=stack, source=source, preset=args.preset, out_path=out)
    print(f"wrote {final}")
    return 0


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
