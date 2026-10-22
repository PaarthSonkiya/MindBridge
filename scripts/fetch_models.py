#!/usr/bin/env python3
"""Download and prepare every model MindBridge needs (run once, online).

    python scripts/fetch_models.py            # everything, NLLB-600M
    python scripts/fetch_models.py --nllb 1.3B
    python scripts/fetch_models.py --only tts,vad

Layout produced under models/ (and recorded in models/manifest.json):

    vad/silero_vad.onnx
    asr/whisper-*-quantized-qcs6490/       Qualcomm AI Hub, w8a16, Hexagon NPU   (qualcomm/fetch_whisper.sh)
    asr/ct2-whisper-small/                 CTranslate2 int8 CPU fallback
    mt/nllb-200-distilled-1.3B-ct2-int8/   CTranslate2 int8
    tts/<voice>/                           one voice per language

After this, the device never needs the network again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
GH = "https://github.com/k2-fsa/sherpa-onnx/releases/download"

ASSETS = {
    "vad": [("vad/silero_vad.onnx", f"{GH}/asr-models/silero_vad.onnx", "MIT (snakers4/silero-vad)")],
    "tts": [
        ("tts/vits-piper-vi_VN-vais1000-medium", f"{GH}/tts-models/vits-piper-vi_VN-vais1000-medium.tar.bz2", "CC BY 4.0 (VAIS-1000 corpus)"),
        ("tts/vits-piper-en_US-amy-low", f"{GH}/tts-models/vits-piper-en_US-amy-low.tar.bz2", "See mimic3-voices (Piper)"),
        ("tts/vits-piper-zh_CN-huayan-medium", f"{GH}/tts-models/vits-piper-zh_CN-huayan-medium.tar.bz2", "See HuaYan_TTS (Piper)"),
        ("tts/sherpa-onnx-supertonic-3-tts-int8-2026-05-11",
         f"{GH}/tts-models/sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2", "MIT (Supertone Supertonic-3)"),
    ],
}
NLLB = {
    "600M": "facebook/nllb-200-distilled-600M",
    "1.3B": "facebook/nllb-200-distilled-1.3B",
}


def log(msg: str):
    print(f"[fetch] {msg}", flush=True)


def download(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    tmp.rename(dest)


def fetch_asset(rel: str, url: str):
    target = MODELS / rel
    if target.exists():
        log(f"have {rel}")
        return
    log(f"downloading {url}")
    if url.endswith(".tar.bz2"):
        with tempfile.TemporaryDirectory() as td:
            arc = Path(td) / "a.tar.bz2"
            download(url, arc)
            with tarfile.open(arc) as t:
                t.extractall(td, filter="data")
            src = Path(td) / Path(url).name.removesuffix(".tar.bz2")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), target)
    else:
        download(url, target)


# Pre-converted CTranslate2 int8 builds published by OpenNMT (the CTranslate2 authors).
NLLB_PREBUILT = {"1.3B": "OpenNMT/nllb-200-distilled-1.3B-ct2-int8"}


def fetch_nllb(size: str, convert: bool = False):
    """600M: convert Meta's weights (needs ~4 GB RAM + torch). 1.3B: OpenNMT's int8 build (conversion needs ~8 GB)."""
    out = MODELS / "mt" / f"nllb-200-distilled-{size}-ct2-int8"
    if (out / "model.bin").exists():
        log(f"have {out.relative_to(ROOT)}")
        return
    repo = NLLB[size]
    from huggingface_hub import hf_hub_download, snapshot_download

    if size in NLLB_PREBUILT and not convert:
        log(f"downloading {NLLB_PREBUILT[size]}")
        snapshot_download(NLLB_PREBUILT[size], local_dir=str(out),
                          allow_patterns=["model.bin", "config.json", "shared_vocabulary.*"])
    else:
        log(f"converting {repo} → CTranslate2 int8 (needs: pip install transformers torch sentencepiece ctranslate2)")
        subprocess.run(
            [sys.executable, "-m", "ctranslate2.converters.transformers", "--model", repo,
             "--quantization", "int8", "--output_dir", str(out), "--force"],
            check=True,
        )
    sp = hf_hub_download(repo, "sentencepiece.bpe.model")
    shutil.copy(sp, out / "sentencepiece.bpe.model")
    shutil.rmtree(out / ".cache", ignore_errors=True)
    (out / "LICENSE.txt").write_text("NLLB-200 weights: CC-BY-NC-4.0 (Meta AI). Non-commercial use.\n")


# English ⇄ Vietnamese translator: VietAI envit5-translation (T5, 275M), int8 CTranslate2 build.
# Pinned to the revision MindBridge was measured with (bench/results/published/mt_compare_*.json).
ENVIT5 = ("luigi000/envit5-translation-ct2-int8", "f68ae0e2639dacde555fe91a36b74d662848d681")


def fetch_envit5():
    out = MODELS / "mt" / "envit5-translation-ct2-int8"
    if (out / "model.bin").exists():
        log(f"have {out.relative_to(ROOT)}")
        return
    from huggingface_hub import snapshot_download

    log(f"downloading {ENVIT5[0]} (VietAI/envit5-translation, int8)")
    snapshot_download(ENVIT5[0], revision=ENVIT5[1], local_dir=str(out),
                      allow_patterns=["model.bin", "config.json", "shared_vocabulary.json", "spiece.model", "README.md"])
    shutil.rmtree(out / ".cache", ignore_errors=True)


def fetch_cpu_whisper():
    """CPU fallback: Whisper-small converted to CTranslate2 (Systran/faster-whisper-small), loaded as int8."""
    out = MODELS / "asr" / "ct2-whisper-small"
    if (out / "model.bin").exists():
        log(f"have {out.relative_to(ROOT)}")
        return
    from huggingface_hub import snapshot_download

    log("downloading Systran/faster-whisper-small (CTranslate2)")
    snapshot_download("Systran/faster-whisper-small", local_dir=str(out),
                      allow_patterns=["model.bin", "config.json", "vocabulary.*", "tokenizer.json"])
    shutil.rmtree(out / ".cache", ignore_errors=True)
    write_whisper_tokens(out / "whisper-tokens.txt")


def write_whisper_tokens(path: Path):
    """Byte-level token table ('<base64 bytes> <id>') from Whisper's multilingual vocabulary.

    Rebuilt from the faster-whisper tokenizer.json (GPT-2 byte-to-unicode mapping), so no extra download."""
    import base64

    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    u2b = {chr(c): b for b, c in zip(bs, cs, strict=True)}
    vocab = json.loads((path.parent / "tokenizer.json").read_text(encoding="utf-8"))["model"]["vocab"]
    lines = []
    for tok, idx in sorted(vocab.items(), key=lambda kv: kv[1]):
        if idx >= 50257:
            continue
        raw = bytes(u2b[ch] for ch in tok if ch in u2b)
        lines.append(f"{base64.b64encode(raw).decode()} {idx}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fetch_qnn_whisper(model: str):
    log(f"fetching Qualcomm AI Hub {model} for QCS6490 (qualcomm/fetch_whisper.sh)")
    subprocess.run(["bash", str(ROOT / "qualcomm" / "fetch_whisper.sh")], check=True, env={**os.environ, "MODEL": model})


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(licenses: dict[str, str]):
    files = []
    for p in sorted(MODELS.rglob("*")):
        if p.is_file() and p.name != "manifest.json" and "espeak-ng-data" not in p.parts:
            files.append({"path": str(p.relative_to(MODELS)), "bytes": p.stat().st_size, "sha256": sha256(p)})
    total = sum(f["bytes"] for f in files)
    (MODELS / "manifest.json").write_text(json.dumps({
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_mb": round(total / 2**20, 1),
        "licenses": licenses,
        "files": files,
    }, indent=2))
    log(f"manifest: {len(files)} files, {total / 2**20:.0f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nllb", default="1.3B", choices=list(NLLB), help="translation model size")
    ap.add_argument("--whisper", default="whisper_large_v3_turbo_quantized,whisper_small_quantized",
                    help="AI Hub Whisper builds for the NPU (comma list)")
    ap.add_argument("--convert", action="store_true", help="convert NLLB from Meta's weights even if a prebuilt exists")
    ap.add_argument("--only", default="", help="comma list: vad,asr_cpu,asr_npu,mt,tts")
    ap.add_argument("--skip-npu", action="store_true", help="skip the Qualcomm AI Hub Whisper download")
    args = ap.parse_args()
    only = set(filter(None, args.only.split(",")))
    want = lambda k: not only or k in only  # noqa: E731

    licenses: dict[str, str] = {}
    for group, items in ASSETS.items():
        if want(group):
            for rel, url, lic in items:
                fetch_asset(rel, url)
                licenses[rel] = lic
    if want("asr_cpu"):
        fetch_cpu_whisper()
        licenses["asr/ct2-whisper-small"] = "MIT (OpenAI Whisper; CTranslate2 conversion by Systran)"
    if want("mt"):
        fetch_envit5()
        licenses["mt/envit5-translation-ct2-int8"] = "OpenRAIL (VietAI envit5-translation)"
        fetch_nllb(args.nllb, args.convert)
        licenses[f"mt/nllb-200-distilled-{args.nllb}-ct2-int8"] = "CC-BY-NC-4.0 (Meta NLLB-200)"
    if want("asr_npu") and not args.skip_npu:
        for model in filter(None, args.whisper.split(",")):
            fetch_qnn_whisper(model)
            licenses[f"asr/{model.replace('_', '-')}-qcs6490"] = "MIT (OpenAI Whisper) / Qualcomm AI Hub Models license"
    write_manifest(licenses)


if __name__ == "__main__":
    main()
