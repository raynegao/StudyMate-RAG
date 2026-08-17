#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required to build the demo video." >&2
  exit 1
fi

OUTPUT_PATH="${1:-output/demo/studymate-rag-demo-75s.mp4}"
mkdir -p "$(dirname "$OUTPUT_PATH")"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -framerate 30 -t 10 -i output/playwright/demo-01-home.png \
  -loop 1 -framerate 30 -t 10 -i output/playwright/demo-02-selected.png \
  -loop 1 -framerate 30 -t 12 -i output/playwright/demo-03-indexed.png \
  -loop 1 -framerate 30 -t 10 -i output/playwright/demo-04-question.png \
  -loop 1 -framerate 30 -t 23 -i output/playwright/demo-05-answer.png \
  -loop 1 -framerate 30 -t 10 -i output/playwright/demo-06-delete-confirm.png \
  -filter_complex \
  "[0:v]format=yuv420p,setpts=PTS-STARTPTS[v0]; \
   [1:v]format=yuv420p,setpts=PTS-STARTPTS[v1]; \
   [2:v]format=yuv420p,setpts=PTS-STARTPTS[v2]; \
   [3:v]format=yuv420p,setpts=PTS-STARTPTS[v3]; \
   [4:v]format=yuv420p,setpts=PTS-STARTPTS[v4]; \
   [5:v]format=yuv420p,setpts=PTS-STARTPTS[v5]; \
   [v0][v1][v2][v3][v4][v5]concat=n=6:v=1:a=0[outv]" \
  -map "[outv]" \
  -c:v libx264 \
  -preset medium \
  -crf 22 \
  -pix_fmt yuv420p \
  -movflags +faststart \
  "$OUTPUT_PATH"

echo "$OUTPUT_PATH"
