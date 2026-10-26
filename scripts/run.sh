#!/usr/bin/env bash
# Start MindBridge on the device and open the UI full-screen.
#   bash scripts/run.sh            # UI + full-screen browser (RB3 Gen 2 on HDMI, or a Mac)
#   bash scripts/run.sh --headless # server only (open http://127.0.0.1:8765 yourself)
# Stop with Ctrl+C in this terminal.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -d .venv ]; then
  if ! .venv/bin/python -c 1 2>/dev/null; then
    echo "The Python environment no longer works (was the folder moved?). Re-run the installer."; exit 1
  fi
  . .venv/bin/activate
fi

# Point the Hexagon DSP loader at the QNN skel libraries shipped inside onnxruntime-qnn (Linux only).
QNN_DIR=""
[ "$(uname -s)" = Linux ] && QNN_DIR="$(python - <<'EOF' 2>/dev/null || true
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

URL="http://127.0.0.1:$PORT"
if [ "${1:-}" != "--headless" ] && [ "$(uname -s)" = Darwin ]; then
  # Chrome as a full-screen app window if installed, otherwise the default browser.
  if [ -d "/Applications/Google Chrome.app" ]; then
    open -na "Google Chrome" --args --app="$URL" --start-fullscreen --autoplay-policy=no-user-gesture-required
  else
    open "$URL"
  fi
elif [ "${1:-}" != "--headless" ] && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
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
