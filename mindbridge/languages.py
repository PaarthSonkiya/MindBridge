"""Language registry: one place that maps a language to every model's code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1, used everywhere in the app
    name: str  # English display name
    native: str  # Native display name (for the UI)
    nllb: str  # NLLB-200 language code
    whisper_token_id: int  # Whisper multilingual language token id
    tts_voice: str  # folder name under models/tts/
    tts_engine: str = "vits"  # vits (Piper/Mimic3) | supertonic


# Whisper multilingual special-token ids (vocab size 51865 — tiny/base/small/medium).
WHISPER_EOT = 50257
WHISPER_SOT = 50258
WHISPER_TRANSLATE = 50358
WHISPER_TRANSCRIBE = 50359
WHISPER_NO_SPEECH = 50362
WHISPER_NO_TIMESTAMPS = 50363
WHISPER_FIRST_TIMESTAMP = 50364

LANGUAGES: dict[str, Language] = {
    "vi": Language("vi", "Vietnamese", "Tiếng Việt", "vie_Latn", 50278, "vits-piper-vi_VN-vais1000-medium"),
    "en": Language("en", "English", "English", "eng_Latn", 50259, "vits-piper-en_US-amy-low"),
    # Supertonic-3 (MIT, 31 languages) is far more intelligible in Korean than the Mimic3 KSS voice.
    "ko": Language("ko", "Korean", "한국어", "kor_Hang", 50264, "sherpa-onnx-supertonic-3-tts-int8-2026-05-11", "supertonic"),
    "zh": Language("zh", "Chinese", "中文", "zho_Hans", 50260, "vits-piper-zh_CN-huayan-medium"),
}

# The competition's registered pairs. Vietnamese is always one side.
PAIRS: list[tuple[str, str]] = [("vi", "en"), ("vi", "ko"), ("vi", "zh")]


def get(code: str) -> Language:
    try:
        return LANGUAGES[code]
    except KeyError as exc:
        raise ValueError(f"Unsupported language '{code}'. Supported: {sorted(LANGUAGES)}") from exc


def pair_key(a: str, b: str) -> str:
    return f"{a}-{b}"
