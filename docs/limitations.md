# AutoCam limitations & known gaps

A frank list of where AutoCam isn't pulling its weight yet, so you can
decide whether it fits your workflow.

## Deferred sub-phases

These are committed to land but haven't shipped yet. PLAN.md tracks them:

- **5b — `raw.develop` / `raw.demosaic` op-stack ops.** RAW conversion
  today is fixed at load: AHD demosaic, camera WB, no auto-bright,
  linear gamma. Re-developing with different params requires re-loading
  the file. Op-stack-driven redevelop conflicts with the current "ops
  mutate the live linear buffer" model; we'll add it when there's a
  user need.
- **6b — AI masks (`mask.semantic`, `mask.background`, `mask.face`).**
  The mask infrastructure (`Op.mask`, `MaskOp` base, executor
  composition) is in place; FastSAM / rembg / MediaPipe ride in once
  we settle the easy-install story (Phase 10) — those weights are
  100–200 MB each and need lazy download + caching.
- **7b — `struct.canvas` and `struct.composite`.** Canvas overlaps
  with pad/resize for v1; composite needs a nested-`EditStack` JSON
  layer-model change.
- **8b — `:batch match`.** LLM-driven look-matching across a glob.
  Wants a cost-aware UX (cap, warn, dry-run) and its own review.

## RAW

- **Fuji X-Trans** sensors look soft via AHD. Native X-Trans demosaic
  is a 5b follow-up.
- **Sigma Foveon** isn't on the supported list; works through LibRaw
  only as a Bayer fallback, which isn't right.
- **No EXIF round-trip.** Original camera EXIF / IPTC isn't carried
  onto exports today.
- **60 MP RAWs use ~720 MB working memory** at full res. Tile-based
  export is a Phase 9b polish item; cap `--workers` low for now.

## Tool surface

- **No HSL op.** PLAN spec has it; implementation routed through
  `mask_color_range` + adjustment for v1.
- **No dehaze, no clarity.** Local-contrast ops land in 9b.
- **No noise reduction.** Recovery beyond ~+1.5 EV will reveal sensor
  noise without recourse.

## TUI

- **No history scrubbing yet.** You can `:undo` / `:redo` from the tail
  of the stack, but you can't preview the photo at an arbitrary mid-stack
  point. Phase 9b.
- **No file picker modal.** `:open <path>` is the only way to load.
- **`?` binding** opens the help text in chat — there's no modal screen
  yet (also 9b).

## Export

- **`:export archival`** isn't shipped — Pillow's 16-bit RGB TIFF support
  is fragile, and we'd rather route through `tifffile`. 9b territory.
- **No colour-managed export.** Output is sRGB JPEG / PNG / TIFF only;
  no ICC profile assignment / conversion.

## Distribution

- **Not on PyPI yet.** Install from source for now; Phase 10 ships
  `pip install autocam` and a `curl | sh` bootstrap.
- **No Homebrew formula.** Probably never; we're betting on
  `uv tool install autocam` instead.
- **Windows isn't tested.** Should work via WSL; native Windows is a
  later concern.

## Privacy / security

- **Image data goes to Anthropic.** Plain-English chat sends the current
  preview (≤ 1024 px PNG) and the stack JSON to the Anthropic API. If
  that's not OK for a particular photo, drive AutoCam by `:add` ops only
  and skip the chat.
- **No telemetry.** AutoCam itself doesn't phone home.

## What works really well today

For balance — these are reliable:

- Single-image edits via natural language on JPEG / PNG / TIFF / RAW.
- Mask-scoped local edits via luminosity bands or hue clusters.
- Multi-image batch via `create batch …` / `:batch apply`.
- Reproducible exports — the JSON stack is the source of truth, every
  export regenerates from it.
- `/critique` for read-only photo analysis without mutating the stack.
