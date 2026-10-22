#!/usr/bin/env bash
# One-time ONLINE setup on a Qualcomm RB3 Gen 2 running Ubuntu 24.04 (desktop image).
# After this finishes, unplug the network: MindBridge never needs it again.
#
#   git clone https://github.com/PaarthSonkiya/MindBridge && cd MindBridge
#   bash scripts/setup_rb3.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== System packages"
sudo add-apt-repository -y ppa:ubuntu-qcom-iot/qcom-ppa || true
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev libportaudio2 libsndfile1 alsa-utils chromium-browser || \
  sudo apt-get install -y python3-venv python3-dev libportaudio2 libsndfile1 alsa-utils
# Hexagon NPU user-space (FastRPC). Package names differ between Qualcomm PPA releases; install what exists.
for pkg in qcom-fastrpc1 qcom-fastrpc-dev libqnn1 qnn-tools; do
  if apt-cache show "$pkg" >/dev/null 2>&1; then sudo apt-get install -y "$pkg"; fi
done
# Let the current user open /dev/fastrpc-* without sudo.
if ls /dev/fastrpc-* >/dev/null 2>&1; then
  echo 'KERNEL=="fastrpc-*", MODE="0666"' | sudo tee /etc/udev/rules.d/90-fastrpc.rules >/dev/null
  sudo udevadm control --reload-rules && sudo udevadm trigger || true
fi
sudo usermod -aG audio "$USER" || true

echo "== Python environment"
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "== Models"
pip install "qai_hub_models_cli>=0.65"
python scripts/fetch_models.py --only vad,asr_cpu,tts,asr_npu
if [ ! -f models/mt/nllb-200-distilled-600M-ct2-int8/model.bin ]; then
  echo "Translation model not found. Build it on a laptop with: python scripts/fetch_models.py --only mt"
  echo "then copy models/mt/ to this device (or install the offline bundle)."
fi

echo "== Self-check"
python -m mindbridge doctor || true
echo
echo "Done. Turn the network off, then start MindBridge with:  bash scripts/run.sh"
