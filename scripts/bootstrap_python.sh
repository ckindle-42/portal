#!/usr/bin/env bash
set -euo pipefail

# Standardized Python bootstrap for local dev across Linux/macOS package managers.
if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "ERROR: python3.11/python3 not found. Install Python 3.11 first." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
# Install with all extras + dev tools (testing, linting, typing)
pip install -e ".[dev]"

echo "Bootstrap complete using: $PYTHON_BIN"
echo "Run tests:  python -m pytest tests/"
echo "Run lint:   ruff check src/"
