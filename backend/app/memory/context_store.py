"""Shared Context Memory.

An in-process store of conversation turns per session. It keeps the engine
aware of previous messages, active tasks, equipment references and safety
observations so it can maintain continuity across a shift and generate
handover reports. For a single-node edge device this is sufficient; a
production deployment would back this with SQLite or Redis behind the same
interface.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.schemas import Intent, RiskLevel


@dataclass
class Turn:
    timestamp: str
    speaker: str
    text: str
    intent: Intent
    risk_level: RiskLevel
    hazards: list[str] = field(default_factory=list)
    understanding_score: int | None = None


@dataclass
class Session:
    session_id: str
    turns: list[Turn] = field(default_factory=list)


class ContextStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def add_turn(self, session_id: str, turn: Turn) -> None:
        with self._lock:
            session = self._sessions.setdefault(session_id, Session(session_id))
            session.turns.append(turn)

    def get(self, session_id: str) -> Session:
        with self._lock:
            return self._sessions.get(session_id, Session(session_id))

    def recent_context(self, session_id: str, limit: int = 5) -> str:
        """A compact textual summary of recent turns for prompt grounding."""
        session = self.get(session_id)
        lines = [f"{t.speaker}: {t.text}" for t in session.turns[-limit:]]
        return "\n".join(lines)

    def equipment_referenced(self, session_id: str) -> list[str]:
        session = self.get(session_id)
        refs: set[str] = set()
        for turn in session.turns:
            refs |= set(re.findall(r"\b[A-Z][a-zA-Z]*\s?[A-Z0-9]+\b", turn.text))
            refs |= set(re.findall(r"\b[A-Z]{2,}\b", turn.text))
        return sorted(refs)

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
