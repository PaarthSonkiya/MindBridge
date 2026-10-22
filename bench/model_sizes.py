#!/usr/bin/env python3
"""File-size record of every model MindBridge ships (evidence for the "model size" criterion).

    python bench/model_sizes.py --out bench/results/published/model_sizes.json

Sizes are bytes on disk of the model files (MB = 2^20 bytes). Groups show what each demo
configuration actually loads.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mindbridge import languages as L  # noqa: E402
from mindbridge.config import load_config  # noqa: E402


def dir_bytes(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "bench" / "results" / "published" / "model_sizes.json"))
    args = ap.parse_args()
    cfg = load_config()
    mp = cfg.models_path

    models = {}
    for group in ("vad", "asr", "mt", "tts"):
        for p in sorted((mp / group).iterdir()) if (mp / group).exists() else []:
            if p.name.startswith(".") or not p.exists():
                continue
            models[f"{group}/{p.name}"] = dir_bytes(p.resolve() if p.is_symlink() else p)

    def mb(keys):
        return round(sum(models.get(k, 0) for k in keys) / 2**20, 1)

    vad = "vad/silero_vad.onnx"
    asr = f"{cfg.asr.qnn_model_dir}".replace("\\", "/")
    tts = {code: f"tts/{lang.tts_voice}" for code, lang in L.LANGUAGES.items()}
    groups = {
        "VI ⇄ EN demo (NPU)": [vad, asr, cfg.mt.en_vi_model_dir, tts["vi"], tts["en"]],
        "VI ⇄ KO demo (NPU)": [vad, asr, cfg.mt.en_vi_model_dir, cfg.mt.model_dir, tts["vi"], tts["ko"]],
        "VI ⇄ ZH demo (NPU)": [vad, asr, cfg.mt.en_vi_model_dir, cfg.mt.model_dir, tts["vi"], tts["zh"]],
        "CPU fallback speech recognition": [cfg.asr.cpu_model_dir],
    }
    # What scripts/fetch_models.py installs and the offline package ships.
    shipped = [vad, asr, "asr/whisper-small-quantized-qcs6490", cfg.asr.cpu_model_dir, cfg.mt.en_vi_model_dir,
               cfg.mt.model_dir, *tts.values()]
    report = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "unit": "MB (2^20 bytes) of model files on disk",
        "models_mb": {k: round(v / 2**20, 1) for k, v in models.items()},
        "loaded_per_configuration_mb": {name: {"total": mb(keys), "models": keys} for name, keys in groups.items()},
        "shipped_models": shipped,
        "all_shipped_models_mb": mb(shipped),
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
