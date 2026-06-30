"""Expertise Adaptation Engine.

Adapts a message to the listener's role and technical depth. An engineer keeps
the precise terminology; an operator or trainee receives the same instruction
in plain language with jargon expanded inline.
"""

from __future__ import annotations

import re

from app.engine.lexicon import GLOSSARY
from app.models.schemas import Expertise


def adapt_for_expertise(text: str, expertise: Expertise) -> tuple[str, list[str]]:
    """Return ``(adapted_text, key_points)`` for the given expertise level."""
    key_points = _extract_key_points(text)

    if expertise == Expertise.ENGINEER:
        # Engineers keep full technical fidelity.
        return text, key_points

    adapted = text
    explained: list[str] = []
    for term, plain in GLOSSARY.items():
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        if pattern.search(adapted):
            explained.append(term)
            if expertise == Expertise.TRAINEE:
                # Trainees get the full plain-language replacement.
                adapted = pattern.sub(plain, adapted, count=1)
            else:
                # Operators/technicians keep the term but get an inline gloss.
                adapted = pattern.sub(lambda m, p=plain: f"{m.group(0)} ({p})", adapted, count=1)

    if expertise == Expertise.TRAINEE and key_points:
        adapted = adapted.rstrip(".") + ". Take it one step at a time and ask if unsure."

    return adapted, key_points


def _extract_key_points(text: str) -> list[str]:
    """Pull out the actionable nouns/steps a listener must retain."""
    # Split on common connectors to surface discrete actions.
    pattern = r"[.;]|\bthen\b|\band then\b|\bbefore\b|\bafter\b"
    fragments = re.split(pattern, text, flags=re.IGNORECASE)
    points = []
    for frag in fragments:
        frag = frag.strip(" ,")
        if len(frag.split()) >= 2:
            points.append(frag[0].upper() + frag[1:])
    return points[:6]
