#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"

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

HOST="${STUDYMATE_BACKEND_HOST:-127.0.0.1}"
PORT="${STUDYMATE_BACKEND_PORT:-8000}"

if [[ "${STUDYMATE_BACKEND_RELOAD:-false}" == "true" ]]; then
  exec "$PYTHON_BIN" -m uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --reload
fi

exec "$PYTHON_BIN" -m uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT"
