"""Risk & Safety Intelligence.

Scans a message for hazard signals and assigns a risk level. Safety-critical
messages are flagged so the engine can demand explicit read-back confirmation.
"""

from __future__ import annotations

from app.engine.lexicon import CRITICAL_TERMS, HAZARD_TERMS, HIGH_TERMS
from app.models.schemas import RiskAssessment, RiskLevel


def assess_risk(text: str) -> RiskAssessment:
    lowered = text.lower()
    found: dict[str, str] = {}
    for term, description in HAZARD_TERMS.items():
        if term in lowered:
            found[term] = description

    if not found:
        return RiskAssessment(level=RiskLevel.NONE, rationale="No hazard signals detected.")

    terms = set(found)
    if terms & CRITICAL_TERMS:
        level = RiskLevel.CRITICAL
    elif terms & HIGH_TERMS:
        level = RiskLevel.HIGH
    elif len(terms) >= 2:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    hazards = sorted(set(found.values()))
    requires_confirmation = level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    rationale = (
        f"Detected {len(hazards)} hazard signal(s): " + "; ".join(hazards) + "."
    )
    return RiskAssessment(
        level=level,
        requires_confirmation=requires_confirmation,
        hazards=hazards,
        rationale=rationale,
    )
