"""Translation stage.

Offline mode uses a hand-verified industrial phrase book and falls back to a
clearly-labelled passthrough for unknown phrases — never silently dropping the
message. The Claude path (wired in the pipeline) provides full translation.
"""

from __future__ import annotations

from app.engine.lexicon import EN_VI, VI_EN
from app.models.schemas import Language


def translate_offline(text: str, source: Language, target: Language) -> str:
    if source == target:
        return text

    table = EN_VI if source == Language.EN else VI_EN
    key = text.lower().strip().rstrip(".!?")

    if key in table:
        return _match_punctuation(text, table[key])

    # Phrase-level substitution for known fragments inside a larger sentence.
    rendered = text
    replaced_any = False
    for phrase, translation in sorted(table.items(), key=lambda kv: -len(kv[0])):
        if phrase in rendered.lower():
            rendered = _ci_replace(rendered, phrase, translation)
            replaced_any = True

    if replaced_any:
        return rendered

    # Honest fallback: keep the original and label it rather than fabricate.
    target_name = "Vietnamese" if target == Language.VI else "English"
    return f"{text}  ⟦offline: {target_name} translation needs Claude engine⟧"


def _match_punctuation(original: str, translated: str) -> str:
    trailing = ""
    for ch in reversed(original.strip()):
        if ch in ".!?":
            trailing = ch + trailing
        else:
            break
    return translated + trailing


def _ci_replace(text: str, needle: str, replacement: str) -> str:
    lowered = text.lower()
    idx = lowered.find(needle)
    if idx == -1:
        return text
    return text[:idx] + replacement + text[idx + len(needle) :]
