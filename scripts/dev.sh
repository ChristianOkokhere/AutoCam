#!/usr/bin/env bash
# AutoCam dev loop — lint, format-check, and run tests.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> ruff check"
uv run ruff check src tests

echo "==> ruff format --check"
uv run ruff format --check src tests

echo "==> pytest"
uv run pytest

echo "==> ok"
