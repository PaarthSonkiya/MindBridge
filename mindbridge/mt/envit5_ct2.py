"""English ⇄ Vietnamese translation: VietAI envit5-translation (T5, 275M) on CTranslate2, int8, CPU.

Chosen for the VI ⇄ EN pair because it beats NLLB-200 1.3B there while being 5× smaller and several
times faster (measured: bench/results/published/mt_compare_*.json):

* organisers' VI→EN samples: BLEU 34.97 vs 32.04, chrF++ 54.5 vs 50.9
* FLORES-200 devtest EN→VI: BLEU 42.7 vs 39.5; VI→EN: 38.3 vs 38.2

Input carries a source-language prefix ("vi: …" / "en: …"); the model sometimes echoes a target
prefix, which is stripped.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from mindbridge.mt.nllb_ct2 import MtResult, PhraseCache
from mindbridge.mt.text import keep_final_punctuation, split_sentences

_PREFIX = re.compile(r"^\s*(en|vi)\s*:\s*", re.I)
# "Machine 4" in Title Case is copied through untranslated ("Machine 4"); lower case gives "máy 4".
# A capitalised "Line 2" on a factory floor is a production line, not a bus route ("tuyến 2").
_EQUIP = re.compile(
    r"\b(Machine|Pump|Conveyor|Station|Press|Robot|Oven|Tank|Motor|Mixer|Boiler|Compressor|Furnace|Dryer|"
    r"Cutter|Line)(\s+(?:number\s+|no\.?\s*|#)?\d+)"
)


# envit5 was trained on tokenised English and sometimes writes "Do n't" / "I 've".
_CONTRACTION = re.compile(r"(\w) (n't|'s|'re|'ve|'ll|'d|'m)\b", re.I)


def detokenise_english(text: str) -> str:
    return _CONTRACTION.sub(r"\1\2", text)


_TIME = re.compile(r"\b(\d{1,2}) ?: (\d{2})\b")


def tidy_vietnamese(text: str) -> str:
    """'21: 55' → '21:55'; capital first letter (lower-cased equipment names can start a sentence)."""
    text = _TIME.sub(r"\1:\2", text)
    return text[:1].upper() + text[1:]


def normalise_english(text: str) -> str:
    return _EQUIP.sub(lambda m: ("production line" if m.group(1) == "Line" else m.group(1).lower()) + m.group(2), text)


class Envit5Translator:
    compute_unit = "cpu"
    pairs = frozenset({("en", "vi"), ("vi", "en")})

    def __init__(
        self,
        model_dir: Path,
        beam_size: int = 1,
        threads: int = 4,
        max_decoding_length: int = 256,
        phrasebook: Path | None = None,
    ):
        import ctranslate2
        import sentencepiece as spm

        self.model_dir = Path(model_dir)
        sp_file = self.model_dir / "spiece.model"
        if not sp_file.exists():
            raise FileNotFoundError(f"spiece.model missing in {self.model_dir}")
        self.translator = ctranslate2.Translator(
            str(self.model_dir), device="cpu", compute_type="int8", inter_threads=1, intra_threads=threads
        )
        self.sp = spm.SentencePieceProcessor(model_file=str(sp_file))
        self.beam_size = beam_size
        self.max_len = max_decoding_length
        self.cache = PhraseCache(phrasebook)
        self.name = f"{self.model_dir.name} (CTranslate2 int8, CPU)"
        self._lock = threading.Lock()

    def supports(self, src: str, tgt: str) -> bool:
        return (src, tgt) in self.pairs

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
        return MtResult(" ".join(out), src, tgt, {"mt": (time.perf_counter() - t0) * 1e3})

    def translate_many(self, texts: list[str], src: str, tgt: str) -> list[str]:
        pieces = [split_sentences(t) for t in texts]
        flat = self.translate_batch([p for ps in pieces for p in ps], src, tgt)
        out, i = [], 0
        for ps in pieces:
            out.append(" ".join(flat[i : i + len(ps)]))
            i += len(ps)
        return out

    def translate_batch(self, sentences: list[str], src: str, tgt: str) -> list[str]:
        if not sentences:
            return []
        if not self.supports(src, tgt):
            raise ValueError(f"envit5 translates only English ⇄ Vietnamese, not {src}→{tgt}")
        if src == "en":
            sentences = [normalise_english(s) for s in sentences]
        batch = [self.sp.encode(f"{src}: {s}", out_type=str) + ["</s>"] for s in sentences]
        with self._lock:
            results = self.translator.translate_batch(batch, beam_size=self.beam_size, max_decoding_length=self.max_len)
        outs = [_PREFIX.sub("", self.sp.decode(r.hypotheses[0])).strip() for r in results]
        outs = [detokenise_english(o) for o in outs] if tgt == "en" else [tidy_vietnamese(o) for o in outs]
        return [keep_final_punctuation(s, o, tgt) for s, o in zip(sentences, outs, strict=True)]
