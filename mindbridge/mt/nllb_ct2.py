"""Offline neural machine translation: NLLB-200 (distilled) on CTranslate2, int8, CPU.

Why CPU and not the NPU: NLLB is an autoregressive encoder-decoder with dynamic
shapes; CTranslate2's int8 ARM kernels run it in well under a second per
sentence on the QCS6490's Kryo cores, leaving the Hexagon NPU free for Whisper.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from mindbridge import languages as L
from mindbridge.mt.text import split_sentences


@dataclass
class MtResult:
    text: str
    src_lang: str
    tgt_lang: str
    timings_ms: dict[str, float] = field(default_factory=dict)
    from_cache: bool = False


class PhraseCache:
    """Exact-match cache of verified translations for frequent factory phrases.

    Loaded from ``config/phrasebook.json``; a hit returns instantly and exactly,
    which matters for short safety commands like "Stop the machine".
    """

    def __init__(self, path: Path | None):
        self.table: dict[str, str] = {}
        if path and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for pair, entries in data.items():
                for src, tgt in entries.items():
                    self.table[f"{pair}|{_norm(src)}"] = tgt

    def get(self, src_lang: str, tgt_lang: str, text: str) -> str | None:
        return self.table.get(f"{src_lang}-{tgt_lang}|{_norm(text)}")


def _norm(s: str) -> str:
    return " ".join(s.lower().strip().rstrip(".!?。！？").split())


class NllbTranslator:
    compute_unit = "cpu"

    def __init__(
        self,
        model_dir: Path,
        beam_size: int = 2,
        threads: int = 4,
        max_decoding_length: int = 200,
        phrasebook: Path | None = None,
    ):
        import ctranslate2
        import sentencepiece as spm

        self.model_dir = Path(model_dir)
        self.translator = ctranslate2.Translator(
            str(self.model_dir), device="cpu", compute_type="int8", inter_threads=1, intra_threads=threads
        )
        sp_file = next(iter(sorted(self.model_dir.glob("*.model"))), None)
        if sp_file is None:
            raise FileNotFoundError(f"sentencepiece model missing in {self.model_dir}")
        self.sp = spm.SentencePieceProcessor(model_file=str(sp_file))
        self.beam_size = beam_size
        self.max_len = max_decoding_length
        self.cache = PhraseCache(phrasebook)
        self.name = f"{self.model_dir.name} (CTranslate2 int8, CPU)"
        self._lock = threading.Lock()

    def model_files(self) -> list[str]:
        return [str(p) for p in self.model_dir.iterdir() if p.is_file()]

    def translate(self, text: str, src: str, tgt: str) -> MtResult:
        t0 = time.perf_counter()
        if not text.strip() or src == tgt:
            return MtResult(text, src, tgt, {"mt": 0.0})
        cached = self.cache.get(src, tgt, text)
        if cached is not None:
            return MtResult(cached, src, tgt, {"mt": (time.perf_counter() - t0) * 1e3}, from_cache=True)
        out = self.translate_batch(split_sentences(text), src, tgt)
        joiner = "" if tgt == "zh" else " "
        return MtResult(joiner.join(out), src, tgt, {"mt": (time.perf_counter() - t0) * 1e3})

    def translate_many(self, texts: list[str], src: str, tgt: str) -> list[str]:
        """Translate several multi-sentence texts with ONE model call (sentences split, batched, rejoined)."""
        joiner = "" if tgt == "zh" else " "
        pieces = [split_sentences(t) for t in texts]
        flat = self.translate_batch([p for ps in pieces for p in ps], src, tgt)
        out, i = [], 0
        for ps in pieces:
            out.append(joiner.join(flat[i : i + len(ps)]))
            i += len(ps)
        return out

    def translate_batch(self, sentences: list[str], src: str, tgt: str) -> list[str]:
        if not sentences:
            return []
        s_code, t_code = L.get(src).nllb, L.get(tgt).nllb
        batch = [[s_code, *self.sp.encode(s, out_type=str), "</s>"] for s in sentences]
        with self._lock:
            results = self.translator.translate_batch(
                batch,
                target_prefix=[[t_code]] * len(batch),
                beam_size=self.beam_size,
                max_decoding_length=self.max_len,
                repetition_penalty=1.1,
                no_repeat_ngram_size=4,
            )
        outs = []
        for r in results:
            toks = [t for t in r.hypotheses[0] if t != t_code]
            outs.append(self.sp.decode(toks).strip())
        return outs
