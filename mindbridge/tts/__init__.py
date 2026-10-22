"""Offline speech synthesis: one small VITS voice per language (sherpa-onnx, CPU)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from mindbridge import languages as L

SUPERTONIC_SPEAKER = 6
SUPERTONIC_STEPS = 5  # 5 flow steps: ~0.2 RTF on CPU with no audible loss vs 8 in our tests


@dataclass
class TtsResult:
    audio: np.ndarray
    sample_rate: int
    ms: float


class Tts:
    compute_unit = "cpu"

    def __init__(self, voices_dir: Path, threads: int = 2, speed: float = 1.0):
        self.voices_dir = Path(voices_dir)
        self.threads = threads
        self.speed = speed
        self._voices: dict[str, object] = {}
        self._lock = threading.Lock()

    def voice_dir(self, lang: str) -> Path:
        return self.voices_dir / L.get(lang).tts_voice

    def available(self, lang: str) -> bool:
        return self.voice_dir(lang).exists()

    def _load(self, lang: str):
        if lang in self._voices:
            return self._voices[lang]
        import sherpa_onnx as so

        d = self.voice_dir(lang)
        if L.get(lang).tts_engine == "supertonic":
            st = so.OfflineTtsSupertonicModelConfig(
                duration_predictor=str(d / "duration_predictor.int8.onnx"),
                text_encoder=str(d / "text_encoder.int8.onnx"),
                vector_estimator=str(d / "vector_estimator.int8.onnx"),
                vocoder=str(d / "vocoder.int8.onnx"),
                tts_json=str(d / "tts.json"),
                unicode_indexer=str(d / "unicode_indexer.bin"),
                voice_style=str(d / "voice.bin"),
            )
            cfg = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(supertonic=st, num_threads=self.threads))
            self._voices[lang] = so.OfflineTts(cfg)
            return self._voices[lang]
        onnx = next(p for p in sorted(d.glob("*.onnx")))
        vits = so.OfflineTtsVitsModelConfig(
            model=str(onnx),
            tokens=str(d / "tokens.txt"),
            data_dir=str(d / "espeak-ng-data") if (d / "espeak-ng-data").exists() else "",
            lexicon=str(d / "lexicon.txt") if (d / "lexicon.txt").exists() else "",
        )
        cfg = so.OfflineTtsConfig(
            model=so.OfflineTtsModelConfig(vits=vits, num_threads=self.threads),
            max_num_sentences=2,
        )
        self._voices[lang] = so.OfflineTts(cfg)
        return self._voices[lang]

    def preload(self, langs: list[str]) -> None:
        for lang in langs:
            if self.available(lang):
                self._load(lang)

    def synthesize(self, text: str, lang: str) -> TtsResult:
        t0 = time.perf_counter()
        with self._lock:
            tts = self._load(lang)
            if L.get(lang).tts_engine == "supertonic":
                import sherpa_onnx as so

                g = so.GenerationConfig()
                g.sid, g.num_steps, g.speed = SUPERTONIC_SPEAKER, SUPERTONIC_STEPS, 1.05 * self.speed
                g.extra = {"lang": lang}  # assign the dict; item assignment is silently dropped
                out = tts.generate(text, g)
            else:
                out = tts.generate(text, sid=0, speed=self.speed)
        audio = np.asarray(out.samples, dtype=np.float32)
        # 150 ms lead-in: many USB/HDMI audio paths clip the first syllable while waking up.
        audio = np.concatenate([np.zeros(int(0.15 * out.sample_rate), np.float32), audio])
        return TtsResult(audio, int(out.sample_rate), (time.perf_counter() - t0) * 1e3)

    def model_files(self, langs: list[str]) -> list[str]:
        files: list[str] = []
        for lang in langs:
            d = self.voice_dir(lang)
            files += [str(p) for p in d.glob("*.onnx")]
        return files
