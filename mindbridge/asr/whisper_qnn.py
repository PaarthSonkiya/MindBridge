"""Whisper on the Hexagon NPU, using Qualcomm AI Hub's compiled encoder/decoder.

The model pair is exported by Qualcomm AI Hub (``whisper_small_quantized``,
w8a16) for the QCS6490. The I/O contract (from qai_hub_models' HfWhisper):

* encoder: ``input_features`` (1, 80, 3000) → ``k_cache_cross_i`` / ``v_cache_cross_i``
* decoder (one token per call, static shapes, 200-slot self-attention cache):
  ``input_ids`` (1,1) int32, ``attention_mask`` (1,1,1,200) f32,
  ``k/v_cache_self_i_in``, ``k/v_cache_cross_i``, ``position_ids`` (1,) int32
  → ``logits`` (1, 51865, 1, 1), ``k/v_cache_self_i_out``

Decoding is greedy with a forced prompt ``<|sot|><|lang|><|transcribe|><|notimestamps|>``.
Language can be forced (push-to-talk knows who is speaking) or detected from the
first decoder step restricted to the conversation's two languages.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from mindbridge import languages as L
from mindbridge.asr.base import AsrEngine, AsrResult
from mindbridge.asr.mel import log_mel
from mindbridge.asr.tokenizer import WhisperDetokenizer
from mindbridge.ort_qnn import make_session

MASK_NEG = -100.0
DECODE_SLOTS = 200


def _find(model_dir: Path, word: str) -> Path:
    hits = sorted(p for p in model_dir.rglob("*.onnx") if word in p.name.lower())
    if not hits:
        raise FileNotFoundError(f"No *{word}*.onnx under {model_dir}")
    return hits[0]


class WhisperQnn(AsrEngine):
    name = "whisper-small-w8a16 (QNN HTP)"
    compute_unit = "npu"

    def __init__(self, model_dir: Path, backend: str = "qnn", max_tokens: int = 120, threads: int = 4):
        self.model_dir = Path(model_dir)
        self.backend = backend
        self.compute_unit = "npu" if backend == "qnn" else "cpu"
        self.max_tokens = min(max_tokens, DECODE_SLOTS - 6)
        self.encoder_path = _find(self.model_dir, "encoder")
        self.decoder_path = _find(self.model_dir, "decoder")
        self.encoder = make_session(self.encoder_path, backend, threads)
        self.decoder = make_session(self.decoder_path, backend, threads)
        tok = next(iter(sorted(self.model_dir.rglob("*tokens*.txt"))), None)
        if tok is None:
            raise FileNotFoundError(f"Whisper tokens file missing in {self.model_dir}")
        self.detok = WhisperDetokenizer(tok)

        self.enc_in = self.encoder.get_inputs()[0]
        self.enc_out_names = [o.name for o in self.encoder.get_outputs()]
        self.dec_inputs = {i.name: i for i in self.decoder.get_inputs()}
        self.dec_out_names = [o.name for o in self.decoder.get_outputs()]
        self.logits_name = next(n for n in self.dec_out_names if "logit" in n.lower())
        self.self_in = sorted(n for n in self.dec_inputs if "cache_self" in n and n.endswith("_in"))
        for name, spec in [(self.enc_in.name, self.enc_in), *self.dec_inputs.items()]:
            if spec.type != "tensor(float)" and name not in ("input_ids", "position_ids"):
                raise RuntimeError(
                    f"Input '{name}' is {spec.type}; MindBridge expects float I/O. "
                    "Re-export the model from AI Hub without --quantize_io."
                )

    def model_files(self) -> list[str]:
        files = [self.encoder_path, self.decoder_path]
        files += [p for p in self.model_dir.rglob("*.bin")]
        return [str(p) for p in files]

    # ------------------------------------------------------------------
    def _zeros_self_cache(self) -> dict[str, np.ndarray]:
        return {n: np.zeros(self.dec_inputs[n].shape, dtype=np.float32) for n in self.self_in}

    def _step(self, token: int, pos: int, mask: np.ndarray, cache_self: dict, cache_cross: dict):
        feeds = {
            "input_ids": np.array([[token]], dtype=np.int32),
            "attention_mask": mask,
            "position_ids": np.array([pos], dtype=np.int32),
            **cache_self,
            **cache_cross,
        }
        outs = dict(zip(self.dec_out_names, self.decoder.run(self.dec_out_names, feeds), strict=True))
        new_self = {n: outs[n.replace("_in", "_out")] for n in self.self_in}
        return outs[self.logits_name].reshape(-1), new_self

    def transcribe(self, audio: np.ndarray, language: str | None, candidates: list[str] | None = None) -> AsrResult:
        t0 = time.perf_counter()
        feats = log_mel(audio, n_mels=int(self.enc_in.shape[1]))
        t1 = time.perf_counter()
        enc = self.encoder.run(self.enc_out_names, {self.enc_in.name: feats})
        cache_cross = {n: v for n, v in zip(self.enc_out_names, enc, strict=True) if n in self.dec_inputs}
        t2 = time.perf_counter()

        cache_self = self._zeros_self_cache()
        mask = np.full((1, 1, 1, DECODE_SLOTS), MASK_NEG, dtype=np.float32)
        pos = 0

        def feed(tok: int):
            nonlocal cache_self, pos
            mask[0, 0, 0, DECODE_SLOTS - pos - 1] = 0.0
            logits, cache_self = self._step(tok, pos, mask, cache_self, cache_cross)
            pos += 1
            return logits

        logits = feed(L.WHISPER_SOT)
        if language is None:
            cands = candidates or list(L.LANGUAGES)
            ids = [L.get(c).whisper_token_id for c in cands]
            language = cands[int(np.argmax(logits[ids]))]
        for tok in (L.get(language).whisper_token_id, L.WHISPER_TRANSCRIBE):
            feed(tok)
        logits = feed(L.WHISPER_NO_TIMESTAMPS)

        out: list[int] = []
        for step in range(self.max_tokens):
            logits[L.WHISPER_NO_TIMESTAMPS :] = -np.inf  # no timestamps / specials
            logits[L.WHISPER_SOT : L.WHISPER_NO_TIMESTAMPS] = -np.inf
            if step == 0:
                logits[L.WHISPER_EOT] = -np.inf  # suppress blank output
                logits[220] = -np.inf
            tok = int(np.argmax(logits))
            if tok == L.WHISPER_EOT or _looping(out + [tok]):
                break
            out.append(tok)
            logits = feed(tok)
        t3 = time.perf_counter()
        return AsrResult(
            text=self.detok.decode(out),
            language=language,
            backend=self.name if self.backend == "qnn" else self.name.replace("QNN HTP", "CPU"),
            timings_ms={
                "features": (t1 - t0) * 1e3,
                "encoder": (t2 - t1) * 1e3,
                "decoder": (t3 - t2) * 1e3,
            },
            num_tokens=len(out),
        )


def _looping(tokens: list[int], n: int = 4, repeats: int = 3) -> bool:
    """Stop Whisper's classic hallucination loops (same n-gram repeated)."""
    for size in range(1, n + 1):
        span = size * repeats
        if len(tokens) >= span:
            tail = tokens[-span:]
            if all(tail[i] == tail[i % size] for i in range(span)):
                return True
    return False
