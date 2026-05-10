"""Multi-image batch runner.

Applies a saved :class:`EditStack` to a list of source images, writing each
result through ``out_template``. Workers > 1 spread the work across processes
(each worker re-loads the stack, so the GIL is a non-issue).

Failures don't abort the batch — they collect into the result list, and the
caller (CLI / TUI) decides how to surface them.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from autocam.io.image import save_image
from autocam.pipeline.executor import run_stack
from autocam.pipeline.stack import EditStack

DEFAULT_TEMPLATE = "{stem}_autocam.jpg"
_TEMPLATE_TOKENS = {"name", "stem", "ext", "idx", "idx0", "stack_id"}


@dataclass(frozen=True)
class BatchResult:
    """One image's outcome inside a batch run."""

    idx: int  # 1-based for display
    total: int
    source: Path
    output: Path | None
    seconds: float
    ok: bool
    error: str = ""


def stack_short_id(stack_path: Path | str) -> str:
    """Return an 8-char hash of the stack JSON content for {stack_id}."""
    text = Path(stack_path).read_text(encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def resolve_out_template(
    template: str,
    *,
    source: Path,
    idx: int,
    total: int,
    stack_id: str,
    default_ext: str = "jpg",
) -> Path:
    """Format ``template`` against one source image.

    If the template contains no recognised token, treat it as a directory
    and apply :data:`DEFAULT_TEMPLATE` inside it. ``idx`` is zero-based;
    we render it 1-based and zero-padded to the width of ``total``.
    """
    has_token = any(f"{{{tok}}}" in template for tok in _TEMPLATE_TOKENS)
    if not has_token:
        directory = Path(template)
        template = str(directory / DEFAULT_TEMPLATE)
        if "{ext}" in template:
            pass  # template already references {ext}; keep it
        elif default_ext and not Path(template).suffix:
            template = template + f".{default_ext}"

    pad_w = max(2, len(str(total)))
    tokens = {
        "name": source.name,
        "stem": source.stem,
        "ext": source.suffix.lower().lstrip("."),
        "idx": str(idx + 1).zfill(pad_w),
        "idx0": str(idx).zfill(pad_w),
        "stack_id": stack_id,
    }
    out = template
    for key, value in tokens.items():
        out = out.replace(f"{{{key}}}", value)
    return Path(out).expanduser()


def run_one(
    *,
    stack_path: Path,
    source: Path,
    output: Path,
    image_format: str = "jpeg",
    quality: int = 90,
    idx: int = 0,
    total: int = 1,
) -> BatchResult:
    """Apply a stack to a single image and save the result."""
    started = time.monotonic()
    try:
        stack = EditStack.load(stack_path)
        img = run_stack(stack, source=source, preview=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        save_image(img, output, format=image_format, quality=quality)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        return BatchResult(
            idx=idx + 1,
            total=total,
            source=source,
            output=None,
            seconds=time.monotonic() - started,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    return BatchResult(
        idx=idx + 1,
        total=total,
        source=source,
        output=output,
        seconds=time.monotonic() - started,
        ok=True,
    )


def run_many(
    *,
    stack_path: Path,
    sources: Sequence[Path],
    out_template: str = DEFAULT_TEMPLATE,
    workers: int = 0,
    image_format: str = "jpeg",
    quality: int = 90,
    on_event: Callable[[BatchResult], None] | None = None,
) -> list[BatchResult]:
    """Apply a stack to ``sources`` in parallel.

    ``workers <= 1`` runs sequentially in-process — handy for tests and small
    batches. Otherwise the batch runs across a ``ProcessPoolExecutor``.
    """
    if not sources:
        return []

    stack_id = stack_short_id(stack_path)
    total = len(sources)

    def out_for(idx: int, source: Path) -> Path:
        return resolve_out_template(
            out_template, source=source, idx=idx, total=total, stack_id=stack_id
        )

    if workers <= 1:
        results: list[BatchResult] = []
        for i, source in enumerate(sources):
            r = run_one(
                stack_path=stack_path,
                source=Path(source),
                output=out_for(i, Path(source)),
                image_format=image_format,
                quality=quality,
                idx=i,
                total=total,
            )
            results.append(r)
            if on_event is not None:
                on_event(r)
        return results

    pool_size = max(1, min(workers, total, 8))
    results = []
    with ProcessPoolExecutor(max_workers=pool_size) as pool:
        future_to_idx = {}
        for i, source in enumerate(sources):
            fut = pool.submit(
                run_one,
                stack_path=stack_path,
                source=Path(source),
                output=out_for(i, Path(source)),
                image_format=image_format,
                quality=quality,
                idx=i,
                total=total,
            )
            future_to_idx[fut] = i

        for fut in as_completed(future_to_idx):
            r = fut.result()
            results.append(r)
            if on_event is not None:
                on_event(r)

    # Sort by idx so the caller sees a stable order.
    results.sort(key=lambda r: r.idx)
    return results


def expand_inputs(patterns: Iterable[str]) -> list[Path]:
    """Resolve glob patterns + literal paths to a sorted, deduped list."""
    import glob

    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if not matches and Path(pattern).exists():
            matches = [pattern]
        for m in sorted(matches):
            p = Path(m).expanduser().resolve()
            if p not in seen and p.is_file():
                seen.add(p)
                out.append(p)
    return out


def auto_workers() -> int:
    """Pick a sensible default — CPU count, capped at 8."""
    return min(8, os.cpu_count() or 1)
