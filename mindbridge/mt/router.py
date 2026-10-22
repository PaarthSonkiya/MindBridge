"""Pick the best on-device translator for each language pair; load each model only when needed.

* English ⇄ Vietnamese → envit5 (T5, 275M), when installed.
* Everything else (Korean, Chinese, and any pair without envit5) → NLLB-200.

In a VI ⇄ EN session NLLB is never loaded, which saves about 1.4 GB of RAM on the RB3 Gen 2.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from mindbridge.mt.nllb_ct2 import MtResult

log = logging.getLogger("mindbridge.mt")


class MtRouter:
    compute_unit = "cpu"

    def __init__(self, models_path: Path, cfg, phrasebook: Path | None = None):
        self.models_path = Path(models_path)
        self.cfg = cfg
        self.phrasebook = phrasebook
        self._backends: dict[str, object] = {}
        self._lock = threading.Lock()
        self.load_ms: dict[str, float] = {}
        en_dir = getattr(cfg, "en_vi_model_dir", "")
        self.en_vi_dir = (self.models_path / en_dir) if en_dir else None
        if self.en_vi_dir is not None and not (self.en_vi_dir / "model.bin").exists():
            log.warning("EN⇄VI model %s not found; NLLB will translate EN⇄VI", self.en_vi_dir)
            self.en_vi_dir = None

    # ------------------------------------------------------------------ choice
    def backend_key(self, src: str, tgt: str) -> str:
        return "envit5" if self.en_vi_dir is not None and {src, tgt} == {"en", "vi"} else "nllb"

    def _get(self, key: str):
        with self._lock:
            if key in self._backends:
                return self._backends[key]
            t = time.perf_counter()
            if key == "envit5":
                from mindbridge.mt.envit5_ct2 import Envit5Translator

                b = Envit5Translator(self.en_vi_dir, beam_size=self.cfg.en_vi_beam_size, threads=self.cfg.threads,
                                     phrasebook=self.phrasebook)
            else:
                from mindbridge.mt.nllb_ct2 import NllbTranslator

                b = NllbTranslator(self.models_path / self.cfg.model_dir, beam_size=self.cfg.beam_size,
                                   threads=self.cfg.threads, max_decoding_length=self.cfg.max_decoding_length,
                                   phrasebook=self.phrasebook)
            self.load_ms[key] = (time.perf_counter() - t) * 1e3
            log.info("loaded %s in %.0f ms", b.name, self.load_ms[key])
            self._backends[key] = b
            return b

    def for_pair(self, src: str, tgt: str):
        return self._get(self.backend_key(src, tgt))

    def preload(self, langs: list[str]) -> None:
        """Load what a conversation between `langs` needs, including the English pivot used by memory."""
        keys = set()
        for a in langs:
            for b in (*langs, "en"):
                if a != b:
                    keys.add(self.backend_key(a, b))
                    keys.add(self.backend_key(b, a))
        for k in sorted(keys):
            self._get(k)

    # ------------------------------------------------------------------ same API as one translator
    def translate(self, text: str, src: str, tgt: str) -> MtResult:
        return self.for_pair(src, tgt).translate(text, src, tgt)

    def translate_many(self, texts: list[str], src: str, tgt: str) -> list[str]:
        return self.for_pair(src, tgt).translate_many(texts, src, tgt)

    def translate_batch(self, sentences: list[str], src: str, tgt: str) -> list[str]:
        return self.for_pair(src, tgt).translate_batch(sentences, src, tgt)

    @property
    def loaded(self) -> list:
        return list(self._backends.values())

    @property
    def name(self) -> str:
        return " + ".join(b.name for b in self.loaded) or "not loaded yet"

    @property
    def beam_size(self) -> int:
        return self.cfg.beam_size

    def model_files(self) -> list[str]:
        return [f for b in self.loaded for f in b.model_files()]
