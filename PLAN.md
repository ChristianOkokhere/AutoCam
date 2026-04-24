# AutoCam — Build Plan

This document is the authoritative roadmap for building AutoCam. It is intentionally detailed so we can work from it, peel off phases, and course-correct without losing the thread.

---

## 1. Vision recap

A terminal UI where a user types natural-language instructions, Claude reasons about the image it can see, calls structured tools on a non-destructive edit pipeline, and shows the result back — iterating until the user is happy. No mouse. No sliders. Pure NL → structured ops → pixels.

## 2. Core principles (non-negotiable)

| Principle | Implication |
|---|---|
| No UX, pure NL | Every capability — including masking, compositing, metadata — is a text-addressable tool. |
| Non-destructive | Sources are immutable. Edits live as JSON sidecars. Output is regeneratable. |
| Semantic masks | Local edits use luminosity / color-range / AI segmentation — never mouse-painted. |
| Fast preview, pro export | Preview pipeline uses downscaled images (≤ 2048px long edge). Export runs full-res. |
| Taste-as-code | Editing technique is captured in a versioned recipe library and fed to the LLM. |
| Tool-first, chat-second | Every change goes through a tool call so every change is auditable and replayable. |

## 3. Architecture at a glance

```
┌───────────────────────────────── Textual App ─────────────────────────────────┐
│                                                                                │
│   Chat Pane (streaming)   Preview Pane (Kitty/iTerm)   History Pane (stack)    │
│                                                                                │
└────────────────┬───────────────────────────────────────────────────────────────┘
                 │
                 ▼
     ┌──────────────────────────┐
     │  Agent Loop              │
     │  ─ build vision message  │
     │  ─ call Claude w/ tools  │
     │  ─ execute tool calls    │
     │  ─ regen preview         │
     │  ─ loop until stop       │
     └───────┬──────────────────┘
             │
             ▼
     ┌──────────────────────────┐       ┌───────────────────────────┐
     │  Edit Stack              │◀──────│  Ops Registry (~45 tools) │
     │  append-only list of ops │       │  tone / color / curve /   │
     │  serializable to JSON    │       │  detail / mask / geom /   │
     └───────┬──────────────────┘       │  compose / raw / export   │
             │                          └───────────────────────────┘
             ▼
     ┌──────────────────────────┐
     │  Pipeline Executor       │
     │  ─ preview path (libvips)│
     │  ─ export path (rawpy+pil│
     └──────────────────────────┘
```

## 4. Repo layout (target)

```
AutoCam/
├── README.md
├── PLAN.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── src/autocam/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py                    # Textual entrypoint
│   ├── config.py                 # env, paths, defaults
│   ├── logging_setup.py
│   │
│   ├── pipeline/
│   │   ├── stack.py              # EditStack, Op dataclasses
│   │   ├── executor.py           # runs stack against an image
│   │   ├── preview.py            # fast pipeline (downscaled)
│   │   └── export.py             # full-res + rawpy
│   │
│   ├── ops/                      # all image operations
│   │   ├── base.py               # Op protocol + registry
│   │   ├── tone.py               # exposure, contrast, highlights, shadows, ...
│   │   ├── color.py              # WB, saturation, vibrance, HSL
│   │   ├── curve.py              # parametric & point curves
│   │   ├── detail.py             # sharpen, NR, clarity
│   │   ├── geometry.py           # crop, rotate, straighten, perspective
│   │   ├── structure.py          # canvas, resize, pad, border, composite
│   │   ├── masks.py              # luminosity, color-range, semantic, face
│   │   ├── raw.py                # RAW-specific (demosaic, camera profile)
│   │   └── export_ops.py         # format, colorspace, metadata
│   │
│   ├── llm/
│   │   ├── client.py             # Anthropic SDK wrapper
│   │   ├── tools.py              # Op → JSONSchema tool spec
│   │   ├── loop.py               # vision + tool-use loop
│   │   └── prompts/
│   │       ├── system.md         # base system prompt
│   │       └── critique.md       # critique-mode prompt
│   │
│   ├── tui/
│   │   ├── screen.py             # three-pane edit screen
│   │   ├── widgets/
│   │   │   ├── chat.py           # streaming chat log
│   │   │   ├── preview.py        # image widget (Kitty/iTerm)
│   │   │   └── history.py        # stack visualization
│   │   └── theme.py
│   │
│   └── io/
│       ├── raw.py                # rawpy wrapper
│       ├── image.py              # Pillow/libvips I/O
│       ├── sidecar.py            # JSON sidecar read/write
│       └── exif.py               # EXIF/IPTC preservation
│
├── knowledge/                    # recipe library (fed to LLM)
│   ├── fundamentals/
│   │   ├── exposure.md
│   │   ├── color_theory.md
│   │   └── working_color_spaces.md
│   └── recipes/
│       ├── portraits/
│       │   └── natural_skin_tones.md
│       ├── landscape/
│       │   └── golden_hour.md
│       ├── bw/
│       │   └── classic_film.md
│       ├── cinematic/
│       │   └── teal_and_orange.md
│       └── fixes/
│           └── underexposed_recovery.md
│
├── tests/
│   ├── fixtures/                 # small test images (ARW, NEF, CR2, JPG)
│   ├── test_pipeline.py
│   ├── test_ops/
│   │   └── test_tone.py
│   └── test_llm/
│       └── test_tool_schema.py
│
└── scripts/
    └── dev.sh
```

## 5. Data model — the edit stack

The edit stack is the heart of the system. Everything else is plumbing.

```json
{
  "version": 1,
  "source": "photos/IMG_0001.arw",
  "source_hash": "sha256:...",
  "created_at": "2026-04-23T10:30:00Z",
  "ops": [
    { "id": "01HT...", "op": "raw.develop",          "params": { "wb": "daylight", "highlights": "recover" } },
    { "id": "01HT...", "op": "tone.exposure",        "params": { "ev": 0.3 } },
    { "id": "01HT...", "op": "tone.shadows",         "params": { "amount": 25 } },
    { "id": "01HT...", "op": "mask.luminosity",      "params": { "range": "highlights", "feather": 0.3 }, "binds_to": "next" },
    { "id": "01HT...", "op": "color.white_balance",  "params": { "temp_shift": -200 }, "mask": "01HT..." },
    { "id": "01HT...", "op": "structure.border",     "params": { "width_pct": 2, "color": "#ffffff" } }
  ]
}
```

Key points:
- **Append-only during a session** — undo removes the tail, redo replays.
- **Each op has a stable ID** — lets masks reference other ops.
- **Masks are ops too** — composed by `mask` field on target ops.
- **Source hash** — detect if the source file has been replaced underneath us.
- **Version field** — let us evolve the schema safely.

## 6. Op design

Every op is a dataclass with:

```python
class Op(Protocol):
    id: str                        # ULID
    name: str                      # e.g. "tone.exposure"
    params: dict[str, Any]         # validated against JSONSchema
    mask: str | None               # id of mask op to apply through

    def apply(self, img: Image, ctx: PipelineCtx) -> Image: ...
    def tool_spec(self) -> dict: ...      # JSONSchema for Claude tool-use
    def describe(self) -> str: ...        # human-readable line for history
```

`tool_spec()` auto-generates the Anthropic tool definition so the tool surface never drifts from the implementation.

## 7. Tool surface (final target ~45)

### Tone (8)
`tone.exposure` · `tone.contrast` · `tone.highlights` · `tone.shadows` · `tone.whites` · `tone.blacks` · `tone.brightness` · `tone.levels`

### Color (10)
`color.white_balance(temp, tint)` · `color.saturation` · `color.vibrance` · `color.hsl(range, h/s/l)` · `color.color_grade(shadows/mids/highs)` · `color.split_tone` · `color.channel_mixer` · `color.to_bw` · `color.lut(file)` · `color.profile_assign`

### Curves (2)
`curve.rgb(points)` · `curve.parametric(hi/mid/lo/darks)`

### Detail (5)
`detail.sharpen(amount, radius, detail)` · `detail.nr_luma` · `detail.nr_chroma` · `detail.clarity` · `detail.dehaze`

### Geometry (5)
`geom.crop(x,y,w,h)` · `geom.rotate(deg)` · `geom.straighten(auto|deg)` · `geom.flip(h|v)` · `geom.perspective(points)`

### Structure / compositing (7)
`struct.canvas(w,h,bg)` · `struct.resize(scale|wh)` · `struct.pad(t,r,b,l,color)` · `struct.border(width_pct, color)` · `struct.composite(layer, blend, opacity)` · `struct.text(content, font, size, pos, color)` · `struct.watermark(file, pos, opacity)`

### Masks (6)
`mask.luminosity(range, feather)` · `mask.color_range(hue, sat_range, feather)` · `mask.semantic(description)` *(SAM2)* · `mask.background()` *(rembg)* · `mask.face()` *(MediaPipe)* · `mask.invert(id)`

### RAW (3)
`raw.develop(wb, highlights, black)` · `raw.demosaic(algo)` · `raw.camera_profile(file|name)`

### Export / metadata (3)
`export.save(path, format, quality, colorspace, resize)` · `meta.set(key, value)` · `meta.strip(keys)`

Ops are grouped in the system prompt by purpose so Claude knows how to chain them.

## 8. The LLM loop

Each user turn:

1. **Build message**
   - Attach latest preview image (PNG, ~1024px long edge) as a vision input.
   - Attach current edit stack (compact JSON) as text.
   - Include user turn.
2. **Call Claude Sonnet 4.6** with full tool set, `tool_choice: auto`, prompt caching enabled on system prompt + recipe library.
3. **Execute tool calls** as Claude emits them. On each call:
   - Validate params against JSONSchema.
   - Append to edit stack.
   - Re-run preview pipeline (incremental where possible).
   - Return a small tool result: `{ ok: true, preview_hash: "...", histogram_summary: {...} }`.
4. **Let Claude continue** until `stop_reason == "end_turn"`.
5. **Render new preview** in the TUI + stream Claude's text into the chat pane.

Failures:
- Tool raises → return `{ ok: false, error: "..." }` so Claude can correct itself.
- User cancel (Ctrl-C) → abort current turn, preserve stack up to last-committed op.

Context management:
- System prompt (cached): ~5–15k tokens of tool descriptions + core recipes.
- User turn: image (~1600 tokens) + stack summary (~500 tokens) + user text.
- With caching, repeat turns cost roughly per-turn delta, not full re-read.

## 9. Recipe library

Each recipe is a markdown doc with a consistent frontmatter:

```markdown
---
id: portrait.natural_skin_tones
tags: [portrait, skin, color]
trigger_keywords: [portrait, skin, people, face]
---

# Natural skin tones

## When to reach for this
- Subject is a person, skin is visible.
- Skin looks muddy, overly red, or lifeless.

## Decision tree
1. Check WB — skin tone hue cluster in the 20–40° range under daylight.
2. ...

## Typical ops
- color.hsl(range=orange, sat=-10, lum=+5)
- color.white_balance(tint=+3)
- ...

## Pitfalls
- Over-saturating orange creates orange-peel skin.
- ...
```

Recipes are injected into the system prompt. For v1, all of them ship in the prompt (small library). If the library grows past ~20k tokens, we add retrieval: embed recipe headers, retrieve by trigger keywords or image content.

## 10. Phased build plan

Each phase has a goal, deliverables, key decisions resolved inside it, risks, and a rough effort.

---

### Phase 0 — Foundations (0.5 day) — **Status: DONE**

**Shipped:** 2026-04-23 on `feat/phase-0-scaffolding`. DoD met: `uv run python -m autocam` prints the banner and `uv run pytest` passes. Repo structure, `pyproject.toml`, ruff, gitignore, dev script, smoke tests all in place.

**Goal:** Repo is runnable, tests pass, CI green.

**Deliverables**
- `pyproject.toml` (uv or hatch), pinned versions.
- `.gitignore`, `.env.example`, `ruff.toml`.
- `src/autocam/__main__.py` with a placeholder entrypoint.
- `tests/` scaffold with one smoke test.
- `scripts/dev.sh` running lint + tests.
- Optional: GitHub Actions workflow.

**Definition of done:** `uv run python -m autocam` prints a banner; `uv run pytest` passes.

---

### Phase 1 — Core pipeline MVP (2–3 days) — **Status: DONE**

**Shipped:** 2026-04-23 on `feat/phase-1-core-pipeline`. 13 ops implemented (tone ×6, color ×3, curve, crop, sharpen, export.save), JSON edit stack with registry-based dispatch, executor with preview downscale, CLI `create apply`. 38 passing tests cover every op, stack round-trips, executor end-to-end, and CLI.

**Goal:** Apply a JSON edit stack to a JPEG/TIFF and render the result. No TUI, no LLM.

**Deliverables**
- `pipeline/stack.py` — EditStack + Op dataclasses + JSON (de)serialization.
- `pipeline/executor.py` — applies ops sequentially, caches intermediate states.
- `pipeline/preview.py` — reads image, applies stack, returns a preview-sized PIL image.
- **Ops (v1):** `tone.exposure`, `tone.contrast`, `tone.highlights`, `tone.shadows`, `tone.whites`, `tone.blacks`, `color.white_balance`, `color.saturation`, `color.vibrance`, `curve.rgb`, `geom.crop`, `detail.sharpen`, `export.save`.
- CLI: `create apply --stack edits.json --in photo.jpg --out out.jpg`.
- Fixture images + unit tests comparing against golden outputs.

**Decisions resolved**
- Working color space: **linear sRGB** in float32 during pipeline, sRGB 8-bit on output.
- Preview size: longest edge clamped to 2048px.
- Use libvips for resize/crop/color math where it beats Pillow on speed.

**Risks**
- Highlight/shadow recovery done naively looks bad. Use a **tone-curve-based** implementation (Reinhard-ish) in v1; refine later.
- Color-managed input (embedded ICC profiles) — handle explicitly; don't assume sRGB.

**Effort:** 2–3 days.

---

### Phase 2 — TUI shell (2 days) — **Status: NEXT**

**Goal:** Textual app with three panes, image preview renders, manual op insertion works end-to-end. Bare `create` (no args) launches the TUI; `create apply ...` keeps the one-shot batch mode.

**Deliverables**
- `tui/screen.py` — three-pane layout: chat (left), preview (center), history (right).
- `tui/widgets/preview.py` — image widget using Kitty graphics protocol (fallback to iTerm protocol detection).
- `tui/widgets/history.py` — live-updates from the edit stack.
- `tui/widgets/chat.py` — scrollable log, input box.
- Command mode: `:add tone.exposure ev=0.3` for manual testing.
- File picker for initial image load.

**Decisions resolved**
- Use `textual-image` or equivalent for protocol detection.
- Target resolution: preview widget sizes to pane, pipeline regenerates at requested size.

**Risks**
- Image protocol detection can be flaky — test in Ghostty, Kitty, WezTerm, iTerm2. Terminal.app explicitly unsupported.

**Effort:** 2 days.

---

### Phase 3 — LLM integration (2 days)

**Goal:** Type English, get edits.

**Deliverables**
- `llm/client.py` — Anthropic SDK wrapper with retry + streaming.
- `llm/tools.py` — auto-generates tool definitions from registered Ops.
- `llm/loop.py` — full vision + tool-use loop with prompt caching.
- System prompt (`llm/prompts/system.md`) covering:
  - Role + principles
  - Tool taxonomy
  - How to chain mask ops with adjustment ops
  - When to critique vs. when to act
- Streaming rendering into the chat pane.
- Tool call → stack append → preview regen wiring.

**Decisions resolved**
- Model: `claude-sonnet-4-6`. No fallback to smaller.
- Opus escalation: `/deep` command in chat switches next turn to `claude-opus-4-7`.
- Prompt cache: system prompt + recipes cached; user turn fresh.

**Risks**
- Tool-use latency. Mitigation: streaming + responsive preview pane, and tool results include only summaries, not pixels.
- LLM hallucinating params. Mitigation: strict JSONSchema + explicit ranges in tool descriptions.

**Effort:** 2 days.

---

### Phase 4 — Recipe library + prompt engineering (1–2 days)

**Goal:** The LLM edits with *taste*, not just competence.

**Deliverables**
- `knowledge/fundamentals/` — 3 docs (exposure, color theory, color spaces).
- `knowledge/recipes/` — 5 seed recipes (portraits, landscape golden-hour, B&W classic, cinematic teal-orange, underexposed recovery).
- Recipe loader that bundles recipes into the cached system prompt.
- Critique mode (`/critique`): Claude evaluates the current image without editing.
- A few-shot example block showing ideal tool-call sequences for canonical scenarios.

**Decisions resolved**
- All recipes in prompt for v1. Retrieval comes later.
- Recipe format locked (see §9).

**Risks**
- Prompt bloat. Measure: target system prompt ≤ 20k tokens total.

**Effort:** 1–2 days.

---

### Phase 5 — RAW support (2–3 days)

**Goal:** Open `.arw`, `.nef`, `.cr2`, `.dng`, `.raf` and edit.

**Deliverables**
- `io/raw.py` — rawpy wrapper returning linear float32 arrays with embedded camera matrix info.
- `ops/raw.py` — `raw.develop`, `raw.demosaic`, `raw.camera_profile`.
- Dual pipeline:
  - Preview: develop at thumb size, apply stack, render.
  - Export: develop at full size, apply stack, encode.
- EXIF preservation through the export path.
- Tests with small fixture RAWs from 3+ camera makes.

**Decisions resolved**
- Demosaic default: AHD. Expose `raw.demosaic` for advanced users.
- Color profile default: camera-embedded matrix, fall back to daylight sRGB if missing.

**Risks**
- Per-camera quirks (Fuji X-Trans, Sigma Foveon). Scope: support Bayer well in v1; note X-Trans may look soft.
- Memory on 60MP RAWs during export. Mitigation: process in tiles via libvips when file is above a threshold.

**Effort:** 2–3 days.

---

### Phase 6 — Semantic masks + local adjustments (3–4 days)

**Goal:** "Darken the sky, warm only the skin." Just works.

**Deliverables**
- `ops/masks.py` with:
  - `mask.luminosity(range="shadows"|"mids"|"highs"|custom, feather)`
  - `mask.color_range(hue_range, sat_range, lum_range, feather)`
  - `mask.semantic(description)` — FastSAM or MobileSAM; text prompt via CLIP or caption-conditioned segmenter.
  - `mask.background()` — rembg.
  - `mask.face()` — MediaPipe face detection + skin tone refinement.
  - `mask.invert(id)`.
- Pipeline support for masked ops (composite the op's effect through the mask).
- Mask overlay toggle in preview (`:mask show`).
- Bench target: masked preview regen < 500ms on a 2048px image.

**Decisions resolved**
- Segmentation model: FastSAM for general, rembg for BG, MediaPipe for faces. All run locally on CPU (GPU optional on Apple Silicon via MPS).
- Mask representation: float32 0–1 array at preview resolution, regenerated at export time.

**Risks**
- Local segmentation can miss on novel subjects. Mitigation: LLM retries with a different mask description; expose a `mask.debug()` that saves the mask as a file for inspection.
- Model weights are big (~100–200MB). Lazy-download on first use, cache in `~/.cache/autocam/`.

**Effort:** 3–4 days.

---

### Phase 7 — Structure / compositing (1–2 days)

**Goal:** "Scale to 95% and add a 2% white border with a 1px hairline."

**Deliverables**
- `ops/structure.py`: canvas, resize, pad, border, composite, text, watermark.
- Layer model: a composite layer is an edit stack rendered into a transparent buffer.
- Fonts: ship a default sans + serif; allow user-installed fonts by path.

**Effort:** 1–2 days.

---

### Phase 8 — Multi-image / batch (1–2 days)

**Goal:** "Apply this look to the other 49 photos."

**Deliverables**
- `create batch` CLI taking a stack + glob of inputs.
- TUI: `:batch apply <stack> <glob>` and `:batch match <ref> <glob>`.
- Batch export with filename templating (`{name}_{stack_id}.jpg`).
- Parallelism via a worker pool (CPU-bound; `ProcessPoolExecutor`).

**Effort:** 1–2 days.

---

### Phase 9 — Polish & docs (2 days)

**Goal:** First-run friendly.

**Deliverables**
- Undo/redo in TUI + history scrubbing (preview any point in stack).
- Export presets (web, print, archival).
- Keybindings (help overlay).
- Error surfaces (tool failures shown cleanly in chat).
- Docs:
  - Installation & terminal setup
  - Writing recipes
  - Shipping custom tools
  - Known limitations

**Effort:** 2 days.

---

## 11. Total scope & sequencing

| Phase | Days | Cumulative | Status |
|---|---|---|---|
| 0 — Foundations | 0.5 | 0.5 | **DONE** (2026-04-23) |
| 1 — Core pipeline | 2.5 | 3 | **DONE** (2026-04-23) |
| 2 — TUI shell | 2 | 5 | **NEXT** |
| 3 — LLM loop | 2 | 7 | pending |
| 4 — Recipes + prompt | 1.5 | 8.5 | pending |
| 5 — RAW | 2.5 | 11 | pending |
| 6 — Semantic masks | 3.5 | 14.5 | pending |
| 7 — Structure / composite | 1.5 | 16 | pending |
| 8 — Multi-image | 1.5 | 17.5 | pending |
| 9 — Polish | 2 | 19.5 | pending |

**Cumulative shipped:** Phase 0 + Phase 1 = 3 days of plan (actual wall-clock: one session).

**~20 days of focused work** to a serviceable v1. Phases 1–4 (8.5 days) is the usable demo. Phases 5–6 (6 days) unlock RAW and local adjustments — the point where it becomes genuinely useful to a photographer.

## 12. Risks & open questions

**Risks**

| Risk | Likelihood | Mitigation |
|---|---|---|
| RAW color output doesn't match Lightroom | High | Ship with "close enough" and add optional `--engine darktable` later. |
| Preview latency kills the vibe | Medium | libvips + downscaled previews + incremental ops where possible. |
| LLM picks bad tool sequences | Medium | Strong system prompt + recipes + tool result includes histogram summary so LLM can self-correct. |
| Semantic masks fail on tricky subjects | Medium | Expose mask debug + allow falling back to color-range masks. |
| Prompt cost blows up | Low | Prompt caching; recipes stay < 20k tokens. |

**Open questions**

1. Local model for semantic masks — FastSAM vs. MobileSAM vs. SAM2? Need benchmarks on Apple Silicon.
2. Should we ship an optional `--engine darktable` in v1 or defer?
3. Session persistence — save session on quit? Auto-save interval?
4. Licensing — MIT? Apache 2? Something else?
5. How do we distribute? PyPI + `pipx install autocam`? Homebrew tap? Both?

## 13. Out of scope (for v1)

- Raster painting, brush tools, layer masks drawn by hand.
- Video or burst editing.
- Catalog/DAM features (stars, collections, keywords). EXIF/IPTC edits only.
- Cloud sync.
- Plugin system (tools are built-in for v1; plugin API comes in v2).
- Mobile / web UI — terminal only.

## 14. Ship criteria for v1

- [ ] Open a JPEG or RAW in a supported terminal and see a preview.
- [ ] Type natural-language edits and see them applied within ~2 seconds.
- [ ] At least 20 tools wired, all with validated params.
- [ ] 5 recipes shipped; `/critique` works on arbitrary images.
- [ ] Semantic mask works for sky, subject, background on 3 sample images.
- [ ] Batch apply a saved stack to 10 images without crashing.
- [ ] Installable via `pipx install .` from a clean machine in under 2 minutes.

---

## 15. Next concrete step

Phase 2 — TUI shell. Concrete work:

1. Add `textual` to runtime deps.
2. `src/autocam/tui/screen.py` — three-pane layout (chat left, preview center, history right).
3. `src/autocam/tui/widgets/preview.py` — image widget using the Kitty graphics protocol (auto-detects iTerm2 as fallback).
4. `src/autocam/tui/widgets/history.py` — live view over the current edit stack.
5. `src/autocam/tui/widgets/chat.py` — scrollable log + input box (just echoes for now; Phase 3 wires Claude).
6. Command mode: `:add tone.exposure ev=0.3` to manually insert ops for end-to-end testing.
7. Update `cli.main` so bare `create` (no subcommand) launches the TUI instead of printing the banner; keep `create apply ...` for one-shot batch mode.

**DoD:** `create path/to/photo.jpg` opens the TUI, shows the image, and `:add` / undo visibly change the preview.

Phase 1 tools land in the pipeline already — no op work needed in Phase 2, it's purely presentation + manual op wiring.
