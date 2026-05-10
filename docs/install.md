# Installing AutoCam

## Requirements

- **Python 3.12 or newer.** AutoCam uses modern syntax (`X | None`, dataclass
  inheritance with defaults, `match` in places) and won't run on 3.11.
- **A graphics-capable terminal** (see [Terminal support](#terminal-support)).
- **`uv`** for development. Anything else (pip / pipx) works too once we
  publish to PyPI in Phase 10; for now you build from source.
- **An Anthropic API key** if you want the natural-language loop.
  Manual `:add` ops + the batch / export CLI work without one.

## Install (today, from source)

```bash
git clone https://github.com/ChristianOkokhere/AutoCam.git
cd AutoCam
uv sync
uv run create --version
```

The installed entry-point is `create`. The Python package is `autocam`
(`pip install autocam` once it lands on PyPI; until then use `uv tool
install --from . autocam`).

## Set the API key

```bash
export ANTHROPIC_API_KEY=sk-ant-…
```

You can leave it in your shell profile, or drop a `.env` file at the repo
root if you fork — AutoCam doesn't load `.env` automatically yet, that's a
9b polish item.

## Open a photo

```bash
uv run create some_photo.arw       # JPEG / PNG / TIFF / RAW all work
```

Bare `create` opens the TUI with no image; `:open <path>` loads one inside.
The TUI has three panes — chat (left), preview (centre), history (right) —
and a single chat input at the bottom.

In chat:

- **Free text** (anything not starting with `:` or `/`) → Claude vision +
  tool-use loop. Examples in the help screen (`:help` or `?`).
- **Colon commands** (`:add`, `:undo`, `:open`, `:mask show`, …) drive the
  editor by hand.
- **`/critique`** — Claude reads the photo, no edits.
- **`/deep <message>`** — escalate one turn to Claude Opus 4.7.

## Terminal support

AutoCam renders the preview as an actual image inline. The terminal has
to support either the Kitty graphics protocol or Sixel.

| Terminal           | Status                       |
|---                 |---                            |
| Ghostty            | ✅ best (Kitty graphics)      |
| Kitty              | ✅ Kitty graphics             |
| WezTerm            | ✅ Kitty graphics             |
| iTerm2             | ✅ Sixel                       |
| foot, Konsole      | ✅ Sixel                       |
| Windows Terminal   | ✅ Sixel                       |
| macOS Terminal.app | ⚠️  fallback (no inline image) |

`textual-image` auto-detects on launch. If your terminal can't speak any
graphics protocol, the chat / history panes still work but the preview
stays blank.

## Next-up shortcuts

| Action               | Command / binding              |
|---                   |---                              |
| Help                 | `:help` or `?`                 |
| Undo / redo          | `Ctrl+Z` / `Ctrl+Y`            |
| Quit                 | `:quit` or `Ctrl+C`            |
| Mask overlay         | `:mask show last` / `:mask hide` |
| Web JPEG export      | `:export web`                   |
| Print JPEG export    | `:export print`                 |
| Multi-image batch    | `:batch apply <stack> '*.jpg'`  |

## Troubleshooting

- **"`ANTHROPIC_API_KEY not set`"** in chat → export the key in your shell
  before launching.
- **No image in the preview pane** → your terminal probably doesn't
  support a graphics protocol. The history + chat panes still work; or
  use the CLI (`create apply --stack stack.json --in photo.jpg --out
  out.jpg`) if you don't need a live preview.
- **`rawpy` install fails** → on macOS / Linux the wheel ships with
  LibRaw; if it didn't, `brew install libraw` or `apt install
  libraw-dev` and retry `uv sync`.
- **Long batch runs eat memory** → cap `--workers` lower; 60 MP RAWs
  can use ~1 GB per worker.
