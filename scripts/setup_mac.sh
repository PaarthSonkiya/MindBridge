#!/usr/bin/env bash
# One-time ONLINE setup on an Apple Silicon Mac (macOS 14 or later). Needs no admin rights, Homebrew or Xcode.
# After this finishes, MindBridge never needs the network again.
#
#   curl -L -o mindbridge.zip https://github.com/PaarthSonkiya/MindBridge/archive/refs/heads/main.zip
#   unzip -q mindbridge.zip && cd MindBridge-main
#   bash scripts/setup_mac.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "This script is for Apple Silicon Macs (M1 or later). On a Qualcomm RB3 Gen 2 use scripts/setup_rb3.sh."
  exit 1
fi
FREE_GB=$(df -g "$ROOT" | awk 'NR==2 {print $4}')
if [ "${FREE_GB:-0}" -lt 8 ]; then
  echo "Only ${FREE_GB} GB free on this disk; MindBridge needs about 8 GB (models 3.5 GB + Python environment)."
  exit 1
fi

echo "== Python 3.12 (uv, installed in your home folder; no admin needed)"
echo "   If macOS offers to install 'command line developer tools', click Not Now: they are not needed."
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv python install 3.12
rm -rf .venv   # re-running the setup starts from a clean environment (packages come from uv's cache)
uv venv --seed --python 3.12 .venv
. .venv/bin/activate

echo "== Python packages (exact versions from requirements-macos-arm64.lock)"
uv pip install -r requirements-macos-arm64.lock
uv pip install "huggingface_hub>=0.23" "certifi>=2024.2.2"   # only for downloading the models

echo "== Models (about 3.5 GB)"
python scripts/fetch_models.py --target mac

echo "== Microphone permission"
echo "macOS will now ask whether Terminal may use the microphone: click OK / Allow."
python -c "import sounddevice as sd; sd.rec(8000, samplerate=16000, channels=1); sd.wait()" || true

echo "== Self-check"
python -m mindbridge doctor --run || true
cat <<'EOF'

Done. Next:
  1. Turn Wi-Fi off (Control Center → Wi-Fi).
  2. Start MindBridge:   bash scripts/run.sh
  3. The first time you speak, macOS asks whether Terminal may use the microphone: click Allow.
     (Or: System Settings → Privacy & Security → Microphone → turn on Terminal.)
EOF
