"""CPU fallback: Whisper int8 ONNX via sherpa-onnx (no NPU required)."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from mindbridge.asr.base import AsrEngine, AsrResult
from mindbridge.audio.dsp import TARGET_SR


class WhisperSherpa(AsrEngine):
    compute_unit = "cpu"

    def __init__(self, model_dir: Path, prefix: str = "small", threads: int = 4):
        import sherpa_onnx as so

        self._so = so
        self.model_dir = Path(model_dir)
        self.prefix = prefix
        self.threads = threads
        self.name = f"whisper-{prefix}-int8 (CPU, sherpa-onnx)"
        self.enc = self._pick(f"{prefix}-encoder")
        self.dec = self._pick(f"{prefix}-decoder")
        self.tokens = self.model_dir / f"{prefix}-tokens.txt"
        self._recognizers: dict[str, object] = {}

    def _pick(self, stem: str) -> Path:
        for cand in (f"{stem}.int8.onnx", f"{stem}.onnx"):
            p = self.model_dir / cand
            if p.exists():
                return p
        raise FileNotFoundError(f"{stem}*.onnx not found in {self.model_dir}")

    def _rec(self, language: str):
        if language not in self._recognizers:
            self._recognizers[language] = self._so.OfflineRecognizer.from_whisper(
                encoder=str(self.enc),
                decoder=str(self.dec),
                tokens=str(self.tokens),
                language=language,
                task="transcribe",
                num_threads=self.threads,
                tail_paddings=800,
            )
        return self._recognizers[language]

    def model_files(self) -> list[str]:
        return [str(self.enc), str(self.dec), str(self.tokens)]

    def detect_language(self, audio: np.ndarray, candidates: list[str]) -> str:
        """Cheap language ID: transcribe with each candidate and keep the most confident-looking one."""
        best, best_score = candidates[0], -1e9
        for lang in candidates:
            text = self._run(audio, lang)
            score = _script_score(text, lang)
            if score > best_score:
                best, best_score = lang, score
        return best

    def _run(self, audio: np.ndarray, language: str) -> str:
        rec = self._rec(language)
        s = rec.create_stream()
        s.accept_waveform(TARGET_SR, audio)
        rec.decode_stream(s)
        return s.result.text.strip()

    def transcribe(self, audio: np.ndarray, language: str | None, candidates: list[str] | None = None) -> AsrResult:
        t0 = time.perf_counter()
        if language is None:
            language = self.detect_language(audio, candidates or ["vi", "en"])
        text = self._run(audio, language)
        return AsrResult(
            text=text,
            language=language,
            backend=self.name,
            timings_ms={"asr": (time.perf_counter() - t0) * 1e3},
        )


def _script_score(text: str, lang: str) -> float:
    """Fraction of characters in the script we'd expect for ``lang``."""
    if not text:
        return -1.0
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return -1.0

    def frac(pred):
        return sum(1 for c in letters if pred(c)) / len(letters)

    if lang == "ko":
        return frac(lambda c: "가" <= c <= "힣")
    if lang == "zh":
        return frac(lambda c: "一" <= c <= "鿿")
    viet = set("ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ")
    if lang == "vi":
        return frac(lambda c: c.lower() in viet) * 3 + frac(str.isascii) * 0.5
    return frac(str.isascii) - frac(lambda c: c.lower() in viet) * 3
