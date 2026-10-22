"""CPU Whisper on CTranslate2 (int8): the fallback when the NPU is unavailable.

Uses the same numpy log-mel features and byte-level detokenizer as the NPU path, so
Chinese and Korean characters split across BPE tokens are decoded correctly (some
runtimes decode token by token and silently drop those bytes).
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from mindbridge import languages as L
from mindbridge.asr.base import AsrEngine, AsrResult
from mindbridge.asr.mel import log_mel
from mindbridge.asr.tokenizer import WhisperDetokenizer


class WhisperCt2(AsrEngine):
    compute_unit = "cpu"

    def __init__(self, model_dir: Path, threads: int = 4, beam_size: int = 1, max_tokens: int = 160):
        import ctranslate2

        self._ct2 = ctranslate2
        self.model_dir = Path(model_dir)
        self.model = ctranslate2.models.Whisper(
            str(self.model_dir), device="cpu", compute_type="int8", intra_threads=threads
        )
        self.n_mels = int(self.model.n_mels)
        self.n_vocab = 51866 if self.n_mels == 128 else 51865  # large-v3 / turbo use 128 bands
        self.sp = L.whisper_specials(self.n_vocab)
        self.beam_size = beam_size
        self.max_tokens = max_tokens
        tok = next(iter(sorted(self.model_dir.glob("*tokens*.txt"))), None)
        if tok is None:
            raise FileNotFoundError(f"whisper-tokens.txt missing in {self.model_dir}")
        self.detok = WhisperDetokenizer(tok)
        size = "large-v3-turbo" if "turbo" in self.model_dir.name else self.model_dir.name.split("whisper-")[-1]
        self.name = f"whisper-{size}-int8 (CPU, CTranslate2)"

    def model_files(self) -> list[str]:
        return [str(p) for p in self.model_dir.iterdir() if p.is_file()]

    def preload(self, languages: list[str]) -> None:  # one model serves every language
        return None

    def transcribe(self, audio: np.ndarray, language: str | None, candidates: list[str] | None = None) -> AsrResult:
        t0 = time.perf_counter()
        feats = self._ct2.StorageView.from_array(np.ascontiguousarray(log_mel(audio, self.n_mels)))
        t1 = time.perf_counter()
        if language is None:
            cands = candidates or list(L.LANGUAGES)
            probs = dict(self.model.detect_language(feats)[0])
            language = max(cands, key=lambda c: probs.get(f"<|{c}|>", 0.0))
        prompt = [self.sp["sot"], L.get(language).whisper_token_id, self.sp["transcribe"], self.sp["no_timestamps"]]
        res = self.model.generate(
            feats, [prompt], beam_size=self.beam_size, max_length=self.max_tokens,
            suppress_blank=True, repetition_penalty=1.05, no_repeat_ngram_size=0,
        )[0]
        ids = [i for i in res.sequences_ids[0] if i < self.sp["eot"]]
        t2 = time.perf_counter()
        return AsrResult(
            text=self.detok.decode(ids),
            language=language,
            backend=self.name,
            timings_ms={"features": (t1 - t0) * 1e3, "decode": (t2 - t1) * 1e3},
            num_tokens=len(ids),
        )
