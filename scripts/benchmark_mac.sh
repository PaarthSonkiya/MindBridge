#!/usr/bin/env bash
# Run the OneVoice benchmark on a Mac with no network and zip the results to the Desktop.
#   bash scripts/benchmark_mac.sh [samples folder]      (default: ~/onevoice-samples)
# Turn Wi-Fi off and plug in the charger first; it takes about an hour.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DATA="${1:-$HOME/onevoice-samples}"
OUT=bench/results/published
ZIP="$HOME/Desktop/mindbridge-mac-results.zip"

if [ ! -d "$DATA" ]; then
  echo "No sample folder at $DATA."
  echo "Download the organisers' sample recordings and put the unpacked folders there (docs/mac.md, section 3)."
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "MindBridge is not installed yet: run scripts/setup_mac.sh first."; exit 1
fi
# shellcheck disable=SC1091
. .venv/bin/activate

echo "== Text benchmark (written sentences)"
caffeinate -i python bench/run_benchmark.py --data "$DATA" --mode text --require-offline \
  --out "$OUT/mac_m5_text"
echo "== Voice benchmark (recordings)"
caffeinate -i python bench/run_benchmark.py --data "$DATA" --mode voice --require-offline --unscored-audio \
  --out "$OUT/mac_m5_voice"
echo "== Model sizes"
python bench/model_sizes.py > /dev/null

mkdir -p "$(dirname "$ZIP")"
rm -f "$ZIP"
(cd "$OUT" && zip -qr "$ZIP" mac_m5_text mac_m5_voice model_sizes_mac.json)
echo
echo "Done. Results: $ZIP"
echo "Send that file to the team."
