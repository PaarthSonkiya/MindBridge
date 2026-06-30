"""Understanding Score™ — comprehension verification.

The core innovation of MindBridge. Given the original instruction and the
listener's read-back, we estimate the likelihood that the listener actually
understood the message. The offline implementation is fully deterministic and
explainable: every point in the score is traceable to a named factor.

Factors (weighted):
  * Key-point coverage     — did the read-back capture the critical actions?
  * Entity coverage        — were equipment / part references retained?
  * Confirmation language  — did the listener affirm rather than hedge?
  * Conversational clarity — absence of confusion / clarification requests.
  * Contextual consistency — did the read-back avoid contradicting the order?
"""

from __future__ import annotations

import re

from app.models.schemas import UnderstandingFactor

_STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "or", "is", "are", "be", "before", "after",
    "then", "i", "you", "it", "this", "that", "will", "need", "must", "should", "have",
    "for", "on", "in", "at", "with", "please", "make", "sure", "do", "we", "they",
}

_CONFIRM_WORDS = {"confirmed", "understood", "will", "i need to", "copy", "acknowledged",
                  "got it", "roger", "yes", "okay", "ok", "sure"}
_CONFUSION_WORDS = {"what", "huh", "repeat", "again", "don't understand", "dont understand",
                    "not sure", "unclear", "confused", "which", "?"}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9]+", text.lower()) if t not in _STOPWORDS]


def _content_set(text: str) -> set[str]:
    return set(_tokens(text))


def _entities(text: str) -> set[str]:
    """Equipment / part references: capitalised words, codes, and numbers."""
    ents = set(re.findall(r"\b[A-Z][a-zA-Z]*\s?[A-Z0-9]+\b", text))  # e.g. "Filter B", "Pump 3"
    ents |= set(re.findall(r"\b[A-Z]{2,}\b", text))                  # acronyms e.g. LOTO
    ents |= set(re.findall(r"\b\d+\b", text))                        # bare numbers
    return {e.strip().lower() for e in ents}


def score_understanding(
    original: str, readback: str, threshold: int
) -> tuple[int, bool, list[UnderstandingFactor], list[str]]:
    """Compute the Understanding Score and its explainable breakdown."""
    orig_content = _content_set(original)
    read_content = _content_set(readback)

    # --- Key-point / content coverage (40%) ---
    if orig_content:
        covered = orig_content & read_content
        coverage = len(covered) / len(orig_content)
    else:
        coverage = 1.0
    coverage_score = round(coverage * 100)
    missing_tokens = sorted(orig_content - read_content)

    # --- Entity coverage (25%) ---
    orig_entities = _entities(original)
    read_entities = _entities(readback)
    if orig_entities:
        ent_coverage = len(orig_entities & read_entities) / len(orig_entities)
    else:
        ent_coverage = 1.0
    entity_score = round(ent_coverage * 100)
    missing_entities = sorted(orig_entities - read_entities)

    # --- Confirmation language (15%) ---
    low_read = readback.lower()
    has_confirm = any(w in low_read for w in _CONFIRM_WORDS)
    confirm_score = 100 if has_confirm else 55

    # --- Conversational clarity (10%) ---
    has_confusion = any(w in low_read for w in _CONFUSION_WORDS)
    clarity_score = 35 if has_confusion else 100

    # --- Contextual consistency (10%) ---
    # Penalise read-backs that introduce numbers/entities never in the original
    # (a sign of mishearing), reward proportional length.
    invented = read_entities - orig_entities
    length_ratio = min(len(_tokens(readback)) / max(len(_tokens(original)), 1), 1.5)
    consistency_score = 100
    if invented:
        consistency_score -= min(len(invented) * 20, 60)
    if length_ratio < 0.3:
        consistency_score -= 25  # far too short to be a real read-back
    consistency_score = max(consistency_score, 0)

    echoed = len(orig_content & read_content)
    factors = [
        UnderstandingFactor(name="Key-point coverage", score=coverage_score,
                            detail=f"{echoed}/{len(orig_content) or 1} content words echoed back."),
        UnderstandingFactor(name="Entity coverage", score=entity_score,
                            detail="Equipment / part references retained."
                            if not missing_entities else
                            f"Missing reference(s): {', '.join(missing_entities)}."),
        UnderstandingFactor(name="Confirmation language", score=confirm_score,
                            detail="Listener affirmed the instruction." if has_confirm
                            else "No explicit confirmation detected."),
        UnderstandingFactor(name="Conversational clarity", score=clarity_score,
                            detail="No signs of confusion." if not has_confusion
                            else "Listener signalled confusion / asked to repeat."),
        UnderstandingFactor(name="Contextual consistency", score=consistency_score,
                            detail="Read-back is consistent with the instruction."
                            if not invented else
                            f"Introduced unexpected detail(s): {', '.join(sorted(invented))}."),
    ]

    weights = {
        "Key-point coverage": 0.40,
        "Entity coverage": 0.25,
        "Confirmation language": 0.15,
        "Conversational clarity": 0.10,
        "Contextual consistency": 0.10,
    }
    total = round(sum(f.score * weights[f.name] for f in factors))
    total = max(0, min(100, total))

    # Map missing content tokens back to readable phrases.
    missing_points: list[str] = []
    if missing_entities:
        missing_points.extend(f"reference to '{e}'" for e in missing_entities)
    salient_missing = [t for t in missing_tokens if len(t) > 2][:4]
    if salient_missing:
        missing_points.append("details: " + ", ".join(salient_missing))

    understood = total >= threshold
    return total, understood, factors, missing_points


def build_follow_up(understood: bool, missing_points: list[str], readback: str) -> str:
    """Generate the system's next move when understanding is low."""
    if understood:
        return "Confirmed. Understanding verified — safe to proceed."
    parts = ["Let's double-check before proceeding."]
    if missing_points:
        parts.append("Please confirm you also caught: " + "; ".join(missing_points) + ".")
    else:
        parts.append("Could you repeat the instruction back in your own words?")
    return " ".join(parts)
