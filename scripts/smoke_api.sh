#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${STUDYMATE_API_BASE_URL:-http://127.0.0.1:8000}"
API_BASE_URL="${API_BASE_URL%/}"

echo "Checking $API_BASE_URL/health"
curl -fsS "$API_BASE_URL/health" | python -m json.tool

echo "Checking $API_BASE_URL/api/documents"
curl -fsS "$API_BASE_URL/api/documents" | python -m json.tool

echo "Smoke checks passed."
