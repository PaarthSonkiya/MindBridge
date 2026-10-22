#!/usr/bin/env bash
# Download Qualcomm AI Hub's Whisper-Small (w8a16) compiled for the QCS6490 Hexagon NPU.
#
#   precompiled_qnn_onnx  → runs on the RB3 Gen 2 NPU via onnxruntime-qnn (what the device uses)
#   onnx (w8a16 QDQ)      → same I/O contract, runs on any CPU; used to test the decoder loop on a laptop
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

npu_dir="$OUT/whisper-small-quantized-qcs6490"
cpu_dir="$OUT/whisper-small-quantized-onnx"
mkdir -p "$npu_dir" "$cpu_dir"

sdk=()
[ -n "$QAIRT" ] && sdk=(-s "qairt=$QAIRT")

echo "== Assets available for $MODEL on $CHIPSET"
qai-hub-models fetch "$MODEL" -p w8a16 -c "$CHIPSET" -i || true

echo "== NPU build (precompiled QNN ONNX for $CHIPSET)"
qai-hub-models fetch "$MODEL" -r precompiled_qnn_onnx -p w8a16 -c "$CHIPSET" "${sdk[@]}" -o "$npu_dir"

echo "== Portable ONNX build (CPU-testable, same I/O)"
qai-hub-models fetch "$MODEL" -r onnx -p w8a16 -o "$cpu_dir" || echo "(optional) portable ONNX not available"

# Whisper's vocabulary (same for every multilingual size); our detokenizer reads it.
TOK="$OUT/sherpa-onnx-whisper-small/small-tokens.txt"
if [ -f "$TOK" ]; then
  cp "$TOK" "$npu_dir/whisper-tokens.txt"
  cp "$TOK" "$cpu_dir/whisper-tokens.txt"
fi
find "$npu_dir" "$cpu_dir" -maxdepth 3 -type f | sed "s|$ROOT/||"
