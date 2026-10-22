"""Run MindBridge's own Whisper decoding loop against a REAL QCS6490 NPU on Qualcomm AI Hub.

Every encoder/decoder call in ``mindbridge.asr.whisper_qnn.WhisperQnn.transcribe`` becomes an AI Hub
inference job on a hosted Dragonwing RB3 Gen 2, using the same QNN context binaries that ship
on the device. This checks the quantised I/O handling, attention mask, KV-cache feeding and the
forced prompt end to end, without having the board on the desk.

    python qualcomm/aihub_validate_whisper.py --audio sample.wav --lang en --max-tokens 12

It is slow (one job per decoded token) and only meant as a correctness check.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_DIR = ROOT / "models/asr/whisper-small-quantized-qcs6490"
ONNX_TYPES = {1: "tensor(float)", 2: "tensor(uint8)", 4: "tensor(uint16)", 6: "tensor(int32)", 3: "tensor(int8)", 5: "tensor(int16)"}


class RemoteSession:
    """Looks like an onnxruntime.InferenceSession; runs each call as an AI Hub inference job."""

    def __init__(self, onnx_path: Path, hub, device, log):
        import onnx

        m = onnx.load(str(onnx_path), load_external_data=False)

        def spec(v):
            t = v.type.tensor_type
            return SimpleNamespace(name=v.name, type=ONNX_TYPES[t.elem_type], shape=[d.dim_value for d in t.shape.dim])

        self._inputs = [spec(i) for i in m.graph.input]
        self._outputs = [spec(o) for o in m.graph.output]
        ctx = next(a.s.decode() for n in m.graph.node if n.op_type == "EPContext" for a in n.attribute if a.name == "ep_cache_context")
        self.bin = onnx_path.parent / Path(ctx).name
        self.hub, self.device, self.log = hub, device, log
        log(f"uploading {self.bin.name} ({self.bin.stat().st_size / 2**20:.0f} MB)")
        self.model = hub.upload_model(str(self.bin))
        self.calls = 0

    def get_inputs(self):
        return self._inputs

    def get_outputs(self):
        return self._outputs

    def run(self, names, feeds):
        self.calls += 1
        t = time.time()
        job = self.hub.submit_inference_job(
            model=self.model, device=self.device, inputs={k: [v] for k, v in feeds.items()},
            name=f"mindbridge-validate-{self.bin.stem}-{self.calls}",
        )
        out = job.download_output_data()
        if out is None:
            raise RuntimeError(f"inference job failed: {job.url}")
        self.log(f"  {self.bin.stem} call {self.calls}: {time.time() - t:.0f}s {job.url}")
        return [np.asarray(out[n][0]) for n in names]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--max-tokens", type=int, default=12)
    ap.add_argument("--model-dir", default=str(DEFAULT_DIR))
    args = ap.parse_args()

    import qai_hub as hub
    import soundfile as sf

    from mindbridge.asr import whisper_qnn
    from mindbridge.audio import dsp

    out_dir = ROOT / "bench" / "results" / "aihub"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def log(msg):
        print(msg, flush=True)
        lines.append(msg)

    device = hub.get_devices(attributes="chipset:qualcomm-qcs6490")[0]
    log(f"device: {device.name}")
    model_dir = Path(args.model_dir)
    sessions = {}

    def remote(path, backend, threads):  # noqa: ARG001
        sessions[path.name] = RemoteSession(path, hub, device, log)
        return sessions[path.name]

    whisper_qnn.make_session = remote
    eng = whisper_qnn.WhisperQnn(model_dir, backend="qnn", max_tokens=args.max_tokens)
    audio, sr = sf.read(args.audio, dtype="float32", always_2d=False)
    x = dsp.prepare_for_asr(audio, sr)
    res = eng.transcribe(x, args.lang)
    log(f"RESULT ({args.lang}): {res.text!r}  tokens={res.num_tokens}")
    (out_dir / "validate_whisper.json").write_text(json.dumps({
        "device": device.name, "audio": args.audio, "lang": args.lang, "text": res.text,
        "num_tokens": res.num_tokens, "log": lines,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
