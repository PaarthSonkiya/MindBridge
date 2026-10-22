"""Text normalisation around translation: sentence splitting, script fixes."""

from __future__ import annotations

import re
from functools import lru_cache

_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|(?<=[。！？])")


def split_sentences(text: str, max_chars: int = 220) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    parts = [p.strip() for p in _SPLIT.split(text) if p and p.strip()]
    out: list[str] = []
    for p in parts:
        while len(p) > max_chars:  # very long run-on ASR output: cut at a comma
            cut = p.rfind(",", 0, max_chars)
            cut = cut if cut > 40 else max_chars
            out.append(p[: cut + 1].strip())
            p = p[cut + 1 :].strip()
        if p:
            out.append(p)
    return out


@lru_cache(maxsize=1)
def _t2s():
    try:
        import opencc  # opencc-python-reimplemented

        return opencc.OpenCC("t2s")
    except Exception:  # pragma: no cover - optional dependency
        return None


def to_simplified(text: str) -> str:
    """Whisper sometimes writes Traditional characters for Mandarin; the dataset is zho_Hans."""
    cc = _t2s()
    return cc.convert(text) if cc else text


def clean_asr(text: str, lang: str) -> str:
    text = text.strip()
    if lang == "zh":
        text = to_simplified(text)
        text = text.replace(",", "，").replace("?", "？").replace("!", "！")
    return text
