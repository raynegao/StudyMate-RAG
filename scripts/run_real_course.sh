#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
ACTION="${1:-all}"
COURSE_MODE="${STUDYMATE_COURSE_MODE:-generation}"
case "$ACTION" in
  local) COURSE_MODE=retrieval_only; ACTION=all ;;
  prepare|verify) COURSE_MODE=retrieval_only ;;
esac
case "$COURSE_MODE" in
  generation|retrieval_only) ;;
  *) echo "STUDYMATE_COURSE_MODE 必须为 generation 或 retrieval_only" >&2; exit 2 ;;
esac
set -a
# Load credentials without printing them, then pin storage/chunk settings below.
if [[ "$COURSE_MODE" == "generation" && -f .env.local ]]; then
  source .env.local
fi
source config/profiles/real-course-local.env
set +a
export STUDYMATE_CHAT_MODE="$COURSE_MODE"
if [[ "$COURSE_MODE" == "generation" ]]; then
  export STUDYMATE_MIN_RETRIEVAL_SIMILARITY=0.35
fi
export PYTHONPATH="$ROOT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"
export STUDYMATE_UPLOAD_DIR="$ROOT_DIR/data/uploads/real-course-v2"
export STUDYMATE_CHROMA_DIR="$ROOT_DIR/data/chroma_db/real-course-v2"
export STUDYMATE_BACKEND_HOST=127.0.0.1
export STUDYMATE_FRONTEND_HOST=127.0.0.1
export STUDYMATE_BACKEND_PORT="${STUDYMATE_COURSE_BACKEND_PORT:-8001}"
export STUDYMATE_FRONTEND_PORT="${STUDYMATE_COURSE_FRONTEND_PORT:-8502}"
export STUDYMATE_API_BASE_URL="http://127.0.0.1:$STUDYMATE_BACKEND_PORT"
if [[ "$COURSE_MODE" == "retrieval_only" ]]; then
  unset DEEPSEEK_API_KEY
fi
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ "$ACTION" == "--print-config" ]]; then
  exec "$PYTHON_BIN" -c 'import json; from app.core.config import settings; print(json.dumps({"knowledge_base_name":settings.knowledge_base_name,"chat_mode":settings.chat_mode,"max_upload_size_mb":settings.max_upload_size_mb,"top_k":settings.default_top_k,"upload_profile":settings.upload_dir.name,"chroma_profile":settings.chroma_dir.name}, ensure_ascii=False))'
fi
case "$ACTION" in
  all|prepare|verify|backend|frontend) ;;
  *) echo "用法：scripts/run_real_course.sh [all|local|prepare|verify|backend|frontend|--print-config]" >&2; exit 2 ;;
esac

if [[ "$COURSE_MODE" == "generation" && -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "DeepSeek 尚未配置，请在 .env.local 填写 DEEPSEEK_API_KEY；或使用 scripts/run_real_course.sh local。" >&2
  exit 1
fi
STUDYMATE_CHAT_MODE=retrieval_only "$PYTHON_BIN" scripts/prepare_real_course.py
case "$ACTION" in
  prepare) exit 0 ;;
  verify) exec "$PYTHON_BIN" scripts/verify_real_course.py ;;
  backend) exec scripts/run_backend.sh ;;
  frontend) exec env -u DEEPSEEK_API_KEY scripts/run_frontend.sh ;;
esac

# Fail before launching either server if the chosen ports are occupied.
"$PYTHON_BIN" -c 'import os,socket
ports=[int(os.environ[n]) for n in ("STUDYMATE_BACKEND_PORT","STUDYMATE_FRONTEND_PORT")]
sockets=[socket.socket() for _ in ports]
for s,p in zip(sockets,ports):
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(("127.0.0.1",p))
    s.listen(1)'
scripts/run_backend.sh &
backend_pid=$!
env -u DEEPSEEK_API_KEY scripts/run_frontend.sh &
frontend_pid=$!
cleanup() {
  kill "$backend_pid" "$frontend_pid" 2>/dev/null || true
  wait "$backend_pid" "$frontend_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
printf '真实课程资料库：http://127.0.0.1:%s（Ctrl+C 停止服务，资料保留）\n' "$STUDYMATE_FRONTEND_PORT"
printf '问答模式：%s\n' "$COURSE_MODE"
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
  sleep 1
done
exit 1
