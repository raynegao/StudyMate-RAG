#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/backend}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  else
    PYTHON_BIN="python"
  fi
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
