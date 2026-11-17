#!/usr/bin/env bash
# Task runner for the project. Usage: ./run.sh <task>   (./run.sh help lists tasks)
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
PY="python3"; [ -x "$ROOT/.venv/bin/python" ] && PY="$ROOT/.venv/bin/python"
VIDEO_URL="https://www.youtube.com/watch?v=-gXqiZHu2UY"
cli() { (cd "$ROOT/pipeline" && "$PY" -m unloading.cli "$@"); }

case "${1:-help}" in
  setup)      # .venv with the CV dependencies, npm install for the web app
    python3 -m venv .venv
    .venv/bin/pip install -U pip
    .venv/bin/pip install -r pipeline/requirements.txt
    (cd web && npm install) ;;
  video)      # use a local video file: ./run.sh video path/to/file.mp4
    src="${2:?usage: ./run.sh video <path-to-mp4>}"
    ln -sfn "$(cd "$(dirname "$src")" && pwd)/$(basename "$src")" data/raw/unloading.mp4
    if command -v ffmpeg >/dev/null; then   # 720p copy with 2s keyframes, so scrubbing in the app is instant
      ffmpeg -y -loglevel error -i "$src" -an -vf scale=1280:-2 -c:v libx264 -preset veryfast -crf 24 -g 40 \
        -movflags +faststart web/public/video/unloading.mp4
    else cp "$src" web/public/video/unloading.mp4; fi ;;
  fetch)      # download the reference video to data/raw/ and web/public/video/
    "$PY" -m yt_dlp -f "bv*[vcodec^=avc1][height<=720]/b[ext=mp4]" -o data/raw/unloading.mp4 "$VIDEO_URL"
    cp data/raw/unloading.mp4 web/public/video/unloading.mp4 ;;
  demo)       # seed SYNTHETIC data and build analytics (no video needed, about 2s)
    cli --zones "$ROOT/tests/zones_synthetic.json" seed; cli --zones "$ROOT/tests/zones_synthetic.json" refresh ;;
  quick)      # process only the first 20s of the video (sanity check)
    cli detect --max-seconds 20; cli refresh ;;
  detect)     # video -> raw detections (slow)
    shift; cli detect "$@" ;;
  analytics)  # re-run analytics + export (after changing zones or thresholds)
    cli refresh ;;
  pipeline)   # full run: detect -> analytics -> export
    cli detect; cli refresh ;;
  test)       # unit tests + synthetic end-to-end smoke test (standard library, about 2s)
    "$PY" -m unittest discover -s tests -v ;;
  eval)       # score activity labels against evals/activity_labels.csv, print skill ground truth
    "$PY" evals/score_activity.py || true; "$PY" evals/skill_ground_truth.py ;;
  web)        # start the React app on http://localhost:5173
    cd web && npm run dev ;;
  skill-link) # expose the skill to Claude Code in this repo (.claude/skills)
    mkdir -p .claude/skills
    ln -sfn ../../skill/unloading-intel .claude/skills/unloading-intel ;;
  skill-package) # zip the skill with the current store, for upload to claude.ai
    mkdir -p dist skill/unloading-intel/data
    cp data/processed/unloading.db skill/unloading-intel/data/unloading.db
    (cd skill && zip -qr ../dist/unloading-intel.zip unloading-intel -x "*/__pycache__/*")
    echo "dist/unloading-intel.zip ready to upload" ;;
  *)
    echo "Tasks:"; grep -E '^  [a-z-]+\)' "$0" | sed -E 's/^  ([a-z-]+)\)[ ]*# ?(.*)/  \1\t\2/' | expand -t 16 ;;
esac
