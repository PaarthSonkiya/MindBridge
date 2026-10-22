# Contributing to MindBridge

## Development setup (any laptop)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/fetch_models.py --skip-npu     # CPU models; the NPU build needs the QCS6490 assets
python -m mindbridge serve                    # http://127.0.0.1:8765
```

On a laptop, speech recognition runs on the CPU (sherpa-onnx Whisper). On the RB3 Gen 2 it moves to
the Hexagon NPU automatically when `models/asr/whisper-small-quantized-qcs6490/` and `onnxruntime-qnn`
are present.

## Before opening a pull request

```bash
ruff check mindbridge tests bench qualcomm scripts
pytest -q
```

The tests use fake models, so they run without downloads, an NPU or a microphone.

## Rules of the road

- No network calls at run time. `mindbridge/offline_guard.py` blocks them; keep it that way.
- Every new pipeline stage records its time in `Turn.timings_ms`.
- Memory stores operational facts only (instructions, decisions, issues, outcomes), never small talk.
