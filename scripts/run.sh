#!/usr/bin/env bash
# Start MindBridge on the device and open the UI full-screen on the attached display.
#   bash scripts/run.sh            # UI + kiosk browser
#   bash scripts/run.sh --headless # server only (open http://127.0.0.1:8765 yourself)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -d .venv ] && . .venv/bin/activate

# Point the Hexagon DSP loader at the QNN skel libraries shipped inside onnxruntime-qnn.
QNN_DIR="$(python - <<'EOF' 2>/dev/null || true
import onnxruntime_qnn, os
print(os.path.dirname(onnxruntime_qnn.__file__))
EOF
)"
if [ -n "$QNN_DIR" ]; then
  export ADSP_LIBRARY_PATH="$QNN_DIR;/usr/lib/rfsa/adsp;/usr/lib/dsp/cdsp;/dsp"
  export LD_LIBRARY_PATH="$QNN_DIR:${LD_LIBRARY_PATH:-}"
fi

PORT="${MINDBRIDGE_PORT:-8765}"
python -m mindbridge serve --port "$PORT" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT

for _ in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$PORT/api/status" >/dev/null && break
  sleep 1
done

if [ "${1:-}" != "--headless" ] && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  for b in chromium-browser chromium google-chrome firefox; do
    if command -v "$b" >/dev/null; then
      if [ "$b" = firefox ]; then "$b" --kiosk "http://127.0.0.1:$PORT" &
      else "$b" --kiosk --noerrdialogs --disable-translate --no-first-run \
             --autoplay-policy=no-user-gesture-required "http://127.0.0.1:$PORT" & fi
      break
    fi
  done
fi
wait $SERVER
