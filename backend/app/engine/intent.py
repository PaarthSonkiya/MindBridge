"""Intent classification.

Identifies the *purpose* of a message so downstream stages can prioritise and
route it correctly (e.g. an emergency is handled differently from a question).
"""

from __future__ import annotations

from app.engine.lexicon import INTENT_CUES
from app.models.schemas import Intent


def classify_intent(text: str) -> Intent:
    """Return the most likely intent of ``text`` using ordered keyword cues."""
    lowered = f" {text.lower().strip()} "

    if lowered.strip().endswith("?"):
        # A question mark is a strong signal, but emergencies/warnings phrased
        # as questions ("is the gas leaking?!") should still surface as such.
        for label, cues in INTENT_CUES:
            if label in {"emergency", "warning"} and _matches(lowered, cues):
                return Intent(label)
        return Intent.QUESTION

    for label, cues in INTENT_CUES:
        if _matches(lowered, cues):
            return Intent(label)

    return Intent.STATEMENT


def _matches(haystack: str, cues: tuple[str, ...]) -> bool:
    return any(cue in haystack for cue in cues)
