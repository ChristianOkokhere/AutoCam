# AutoCam

**Natural-language RAW photo editor in your terminal.**

AutoCam pairs a modern LLM with a full non-destructive image pipeline and a Claude-Code-style TUI. You describe what you want in English — *"warm the highlights, lift the shadows, add a 2% white border"* — and AutoCam translates that into concrete, auditable edit operations, shows you the result inline, and lets you keep iterating.

No mouse. No panels. No sliders. Intent → pixels.

---

## Why

Real photo editors hide enormous power behind hundreds of sliders across a dozen panels. Most of what makes a photo good is *taste* and *technique*, not knowing where the "dehaze" toggle lives. An LLM with access to the right set of tools and a curated recipe library can apply that taste faithfully — and usually does it faster than you can find the slider.

AutoCam is the client that makes that loop tight enough to feel like magic.

## How it works

```
  You                  Claude                    Pipeline
  ───                  ──────                    ────────
  "warm it up          → adjust_white_balance(+300K)
   a bit and           → adjust_shadows(+25)
   bring the           ← receives new preview image
   shadows up"         → "done — want me to
                          add a subtle border?"
```

Every edit is a structured tool call. Every tool call is appended to a JSON edit stack. The stack is replayable, diffable, non-destructive — your source file is never touched.

## Core principles

1. **No UX, pure NL.** Every capability, including masking and compositing, is reachable from text.
2. **Non-destructive by default.** Sources are immutable. Edits live in sidecars. Exports are regeneratable.
3. **Semantic masks, not mouse masks.** Local adjustments use luminosity / color-range / AI-segmentation tools — the LLM composes them.
4. **Fast preview, pro export.** Interactive previews on a downscaled image; full-resolution processing only at export.
5. **Taste-as-code.** A recipe library of editing techniques ships alongside the app and grows over time.

## Stack

- **Python 3.12**
- **Textual** — TUI framework with native image rendering
- **Pillow + libvips** — fast preview pipeline
- **rawpy** — RAW decode (LibRaw wrapper)
- **Anthropic SDK** — Claude Sonnet 4.6 for vision + tool-use loop
- **SAM2 / rembg / MediaPipe** — semantic masking for local adjustments

## Terminal support

Best experience in terminals that speak the **Kitty graphics protocol**:

- [Ghostty](https://ghostty.org)
- [Kitty](https://sw.kovidgoyal.net/kitty/)
- [WezTerm](https://wezfurlong.org/wezterm/)

[iTerm2](https://iterm2.com/) also works via its inline image protocol. Terminal.app does not support inline images — you will see edits described but not rendered.

## Architecture

```
  ┌─ Textual TUI ───────────────────────────────────┐
  │   Chat pane     │   Preview pane    │  History  │
  └────────┬────────┴───────────────────┴───────────┘
           │
           ▼
     ┌────────────────┐
     │  Claude loop   │   vision + tool-use, prompt-cached
     └────────┬───────┘
              │  tool calls
              ▼
     ┌────────────────┐        ┌──────────────────┐
     │  Edit stack    │ ◀───── │   ~45 tools      │
     │  (JSON)        │        │   tone · color · │
     └────────┬───────┘        │   mask · geom  · │
              │                 │   compose · raw  │
              ▼                 └──────────────────┘
     ┌────────────────┐
     │  Pipeline      │
     │  · preview     │   fast, downscaled
     │  · export      │   full-res
     └────────────────┘
```

## Status

**Pre-alpha — no code yet.** See [`PLAN.md`](./PLAN.md) for the phased build plan and scope.

## Quick start (future)

```bash
pip install autocam
export ANTHROPIC_API_KEY=sk-ant-...
autocam path/to/photo.arw
```

## License

MIT (placeholder — to be confirmed).
