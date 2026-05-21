#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/backend}"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS="${STREAMLIT_BROWSER_GATHER_USAGE_STATS:-false}"

STREAMLIT_BIN="${STREAMLIT_BIN:-}"
if [[ -z "$STREAMLIT_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/streamlit" ]]; then
    STREAMLIT_BIN="$ROOT_DIR/.venv/bin/streamlit"
  else
    STREAMLIT_BIN="streamlit"
  fi
fi

HOST="${STUDYMATE_FRONTEND_HOST:-127.0.0.1}"
PORT="${STUDYMATE_FRONTEND_PORT:-8501}"

exec "$STREAMLIT_BIN" run "$ROOT_DIR/frontend/streamlit_app.py" \
  --server.address "$HOST" \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false
