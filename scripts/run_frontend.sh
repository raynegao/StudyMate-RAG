#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS="${STREAMLIT_BROWSER_GATHER_USAGE_STATS:-false}"

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

HOST="${STUDYMATE_FRONTEND_HOST:-127.0.0.1}"
PORT="${STUDYMATE_FRONTEND_PORT:-8501}"

exec "$PYTHON_BIN" -m streamlit run "$ROOT_DIR/frontend/streamlit_app.py" \
  --server.address "$HOST" \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false
