"""Profile MindBridge's NPU models on real Qualcomm devices with AI Hub.

    export QAI_HUB_API_TOKEN=...            # or run `qai-hub configure --api_token ...` once
    python qualcomm/aihub_profile.py        # profiles Whisper encoder + decoder on QCS6490

Each job runs on a hosted physical device and returns measured on-device
latency, peak memory and the NPU/CPU split per layer. Results are written to
``bench/results/aihub/`` as raw JSON plus a Markdown summary for the report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "bench" / "results" / "aihub"


def _hub():
    """Configure the AI Hub client from $QAI_HUB_API_TOKEN if ~/.qai_hub/client.ini is missing."""
    import subprocess

    token = os.environ.get("QAI_HUB_API_TOKEN")
    cfg = Path.home() / ".qai_hub" / "client.ini"
    if token and not cfg.exists():
        subprocess.run(["qai-hub", "configure", "--api_token", token], check=True, capture_output=True)
    if not cfg.exists():
        sys.exit("Set QAI_HUB_API_TOKEN or run `qai-hub configure --api_token <token>` first.")
    import qai_hub as hub

    return hub


def pick_device(hub, chipset: str, name: str | None):
    if name:
        return hub.Device(name)
    devices = hub.get_devices(attributes=f"chipset:{chipset}")
    if not devices:
        sys.exit(f"No AI Hub device with chipset {chipset}")
    return devices[0]


def find_models(model_dir: Path) -> list[Path]:
    """Prefer QNN context binaries (.bin); otherwise the ONNX files."""
    bins = sorted(p for p in model_dir.rglob("*.bin") if p.stat().st_size > 1_000_000)
    if bins:
        return bins
    return sorted(p for p in model_dir.rglob("*.onnx"))


def summarize(profile: dict) -> dict:
    s = profile.get("execution_summary", {})
    detail = profile.get("execution_detail", [])
    units: dict[str, int] = {}
    for layer in detail:
        u = layer.get("compute_unit", "?")
        units[u] = units.get(u, 0) + 1
    return {
        "inference_ms": round(s.get("estimated_inference_time", 0) / 1000, 2),
        "peak_memory_mb": round(s.get("estimated_inference_peak_memory", 0) / 2**20, 1),
        "first_load_ms": round(s.get("first_load_time", 0) / 1000, 1),
        "warm_load_ms": round(s.get("warm_load_time", 0) / 1000, 1),
        "layers_by_unit": units,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default=str(ROOT / "models/asr/whisper-small-quantized-qcs6490"))
    ap.add_argument("--chipset", default="qualcomm-qcs6490")
    ap.add_argument("--device", default=None, help='exact AI Hub device name, e.g. "RB3 Gen 2 (Proxy)"')
    ap.add_argument("--options", default="--max_profiler_iterations 10")
    args = ap.parse_args()

    hub = _hub()
    device = pick_device(hub, args.chipset, args.device)
    print(f"Device: {device.name} ({args.chipset})")
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    for path in find_models(Path(args.model_dir).resolve()):
        print(f"Uploading {path.name} ({path.stat().st_size / 2**20:.0f} MB) …")
        model = hub.upload_model(str(path))
        job = hub.submit_profile_job(model=model, device=device, name=f"mindbridge-{path.stem}", options=args.options)
        print(f"  profile job {job.job_id}: {job.url}")
        results.append((path, job))

    rows = []
    for path, job in results:
        status = job.wait()
        if not status.success:
            print(f"  {path.name}: FAILED {status.message}")
            rows.append({"model": path.name, "job": job.url, "error": status.message})
            continue
        prof = job.download_profile()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        raw = OUT / f"{path.stem}_{args.chipset}_{stamp}.json"
        raw.write_text(json.dumps(prof, indent=2))
        row = {"model": path.name, "device": device.name, "job": job.url, **summarize(prof)}
        rows.append(row)
        print(f"  {path.name}: {row['inference_ms']} ms, peak {row['peak_memory_mb']} MB, units {row['layers_by_unit']}")

    md = ["| Model | Device | On-device latency | Peak memory | Layers by compute unit | AI Hub job |", "|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            md.append(f"| {r['model']} | {device.name} | failed | | | {r['job']} |")
        else:
            units = ", ".join(f"{k}: {v}" for k, v in r["layers_by_unit"].items())
            md.append(f"| {r['model']} | {r['device']} | {r['inference_ms']} ms | {r['peak_memory_mb']} MB | {units} | {r['job']} |")
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    (OUT / "summary.json").write_text(json.dumps(rows, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()
