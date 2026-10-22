#!/usr/bin/env bash
# Download Qualcomm AI Hub's Whisper (w8a16) compiled for the QCS6490 Hexagon NPU.
#   MODEL=whisper_small_quantized (default) | whisper_large_v3_turbo_quantized | whisper_medium_quantized
#
# Runtime: precompiled_qnn_onnx (QNN context binary wrapped in ONNX) → loaded by onnxruntime-qnn on the device.
# Check the decoder against a real RB3 Gen 2 without the board: qualcomm/aihub_validate_whisper.py
#
# Needs internet once (qaihub-public-assets.s3.us-west-2.amazonaws.com). No AI Hub token required.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/models/asr"
MODEL="${MODEL:-whisper_small_quantized}"
CHIPSET="${CHIPSET:-qualcomm-qcs6490}"
# Match the QAIRT version bundled in onnxruntime-qnn (2.7.0 ships QAIRT 2.51); fall back to latest.
QAIRT="${QAIRT:-}"

command -v qai-hub-models >/dev/null || pip install "qai_hub_models_cli>=0.65"

# e.g. whisper_small_quantized → models/asr/whisper-small-quantized-qcs6490
slug="$(echo "$MODEL" | tr '_' '-')"
npu_dir="$OUT/$slug-${CHIPSET#qualcomm-}"
mkdir -p "$npu_dir"

sdk=()
[ -n "$QAIRT" ] && sdk=(-s "qairt=$QAIRT")

echo "== Assets available for $MODEL on $CHIPSET"
qai-hub-models fetch "$MODEL" -p w8a16 -c "$CHIPSET" -i || true

echo "== NPU build (precompiled QNN ONNX for $CHIPSET)"
qai-hub-models fetch "$MODEL" -r precompiled_qnn_onnx -p w8a16 -c "$CHIPSET" "${sdk[@]}" -o "$npu_dir"

# Whisper's vocabulary (same for every multilingual size); our detokenizer reads it.
TOK="$OUT/sherpa-onnx-whisper-small/small-tokens.txt"
if [ -f "$TOK" ]; then
  cp "$TOK" "$npu_dir/whisper-tokens.txt"
fi
find "$npu_dir" -maxdepth 3 -type f | sed "s|$ROOT/||"
