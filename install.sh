#!/usr/bin/env sh
# AutoCam bootstrap installer.
#
#   curl -fsSL https://raw.githubusercontent.com/ChristianOkokhere/AutoCam/main/install.sh | sh
#
# Detects `uv`, installs it if missing, then installs the `autocam` PyPI
# package via `uv tool install`. Leaves `create` on the user's PATH.
#
# POSIX sh — no Bashisms; should run under dash, ash, and macOS /bin/sh.

set -eu

PACKAGE_NAME="autocam"
COMMAND_NAME="create"

say() {
  printf '%s\n' "$*"
}

err() {
  printf 'error: %s\n' "$*" >&2
}

require() {
  command -v "$1" >/dev/null 2>&1 || {
    err "$1 not found on PATH. Aborting."
    exit 1
  }
}

require curl

if ! command -v uv >/dev/null 2>&1; then
  say "Installing uv (https://docs.astral.sh/uv/)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv's installer writes to ~/.local/bin (Linux) or ~/.cargo/bin (older).
  # Make the new binary visible to the rest of this script.
  if [ -d "$HOME/.local/bin" ]; then
    PATH="$HOME/.local/bin:$PATH"
  fi
  if [ -d "$HOME/.cargo/bin" ]; then
    PATH="$HOME/.cargo/bin:$PATH"
  fi
  export PATH
fi

say "Installing ${PACKAGE_NAME}…"
uv tool install "${PACKAGE_NAME}"

# `uv tool install` puts shims in ~/.local/bin. If it isn't on the user's
# PATH yet, nudge them once instead of failing silently.
if ! command -v "${COMMAND_NAME}" >/dev/null 2>&1; then
  say ""
  say "${COMMAND_NAME} isn't on PATH yet. Add this to your shell profile:"
  say ""
  say "  export PATH=\"\$HOME/.local/bin:\$PATH\""
  say ""
  say "Then open a new shell and run \`${COMMAND_NAME} --help\`."
  exit 0
fi

say ""
"${COMMAND_NAME}" --help || true

say ""
say "AutoCam installed. Next:"
say "  export ANTHROPIC_API_KEY=sk-ant-…   # for natural-language chat"
say "  ${COMMAND_NAME} path/to/photo.jpg"
