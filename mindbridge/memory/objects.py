"""Operational Memory Object — the unit of MindBridge's memory layer."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

KINDS = (
    "instruction",  # do / don't do something (polarity tells which)
    "decision",  # "we will run Line 2 at half speed"
    "issue",  # "Machine 6 is vibrating"
    "commitment",  # "I will replace the valve before night shift"
    "procedure",  # "after changing the filter, run the flush cycle"
    "exception",  # "Machine 4 can only restart if maintenance signs off"
    "outcome",  # "the valve was replaced"
    "question",
    "note",
)


@dataclass
class MemoryObject:
    kind: str
    text_en: str
    text_source: str
    source_lang: str
    speaker_role: str = ""
    subject: str = ""  # canonical equipment entity, e.g. "Machine 4"
    action: str = ""  # surface verb, e.g. "restart"
    action_family: str = ""  # start | stop | enter | repair | load | touch | use
    polarity: str = "info"  # forbid | require | info
    condition: str = ""  # "until the pressure valve is replaced"
    risk: str = "none"  # none | low | medium | high | critical
    hazards: list[str] = field(default_factory=list)
    text_listener: str = ""
    listener_lang: str = ""
    status: str = "active"  # active | resolved | superseded | info
    verified: str = "n/a"  # n/a | pending | confirmed | failed
    needs_verification: bool = False
    resolved_by: int | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    id: int | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["time"] = time.strftime("%H:%M", time.localtime(self.created_at))
        d["card"] = self.card()
        return d

    def card(self) -> list[str]:
        """Three short lines for the badge's e-ink task card."""
        subj = (self.subject or "NOTICE").upper()
        if self.kind == "instruction" and self.polarity == "forbid":
            line2 = f"DO NOT {self.action.upper()}" if self.action else "DO NOT PROCEED"
        elif self.kind == "instruction":
            line2 = (self.action or "ACTION REQUIRED").upper()
        elif self.kind == "issue":
            line2 = "ISSUE REPORTED"
        elif self.kind == "outcome":
            line2 = "RESOLVED"
        else:
            line2 = self.kind.upper()
        line3 = self.condition.upper() if self.condition else ""
        if self.status == "resolved":
            line3 = "CLEARED"
        return [subj, line2, line3[:40]]
