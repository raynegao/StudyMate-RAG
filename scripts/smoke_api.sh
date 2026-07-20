#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  elif command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.12)"
  else
    echo "Python 3.12 is required for JSON validation." >&2
    exit 1
  fi
fi

API_BASE_URL="${STUDYMATE_API_BASE_URL:-http://127.0.0.1:8000}"
API_BASE_URL="${API_BASE_URL%/}"

echo "Checking $API_BASE_URL/health"
curl -fsS "$API_BASE_URL/health" | "$PYTHON_BIN" -m json.tool

echo "Checking $API_BASE_URL/api/documents"
curl -fsS "$API_BASE_URL/api/documents" | "$PYTHON_BIN" -m json.tool

echo "Smoke checks passed."
