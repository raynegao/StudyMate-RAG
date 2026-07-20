#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  elif command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.12)"
  else
    echo "Python 3.12 is required. Create .venv with: uv venv --python 3.12" >&2
    exit 1
  fi
fi

if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))'; then
  echo "Python 3.12 is required; got $($PYTHON_BIN --version 2>&1)." >&2
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON_BIN" -m ruff check backend frontend tests scripts
"$PYTHON_BIN" -m compileall -q backend tests frontend scripts
"$PYTHON_BIN" -m pytest -q

if command -v uv >/dev/null 2>&1; then
  uv pip check --python "$PYTHON_BIN"
else
  "$PYTHON_BIN" -m pip check
fi
