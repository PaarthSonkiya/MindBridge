"""Understand → Verify → Remember → Act.

The engine turns each translated utterance into an Operational Memory Object,
then reasons over the active memory:

* conflict  — a new order contradicts an active restriction ("start Machine 4")
* resolve   — an outcome clears a restriction / issue ("the valve was replaced")
* verify    — a contextual check question for safety-critical instructions
* recall    — answers "can we restart Machine 4?" from the factory's own history
* handover  — a shift summary of everything still open

All answers are composed in English and translated to the asker's language by
the caller, so the same logic serves every language pair.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from mindbridge.memory.extractor import content_words, extract, find_action, find_entities
from mindbridge.memory.objects import MemoryObject
from mindbridge.memory.store import MemoryStore

_NO_EN = re.compile(
    r"\b(no|nope|not|don't|dont|can't|cannot|can not|shouldn't|mustn't|never|wait|not yet|until|unless|forbidden|stop)\b",
    re.I,
)
_YES_EN = re.compile(r"\b(yes|yeah|yep|ok|okay|sure|can|allowed|go ahead|of course)\b", re.I)
_NO_NATIVE = {
    "vi": ("không", "chưa", "đừng", "không được", "cấm"),
    "ko": ("아니", "안 돼", "안돼", "안 됩", "못", "하지 마", "금지", "아직"),
    "zh": ("不", "没", "别", "禁止", "还没"),
    "en": (),
}
_YES_NATIVE = {
    "vi": ("có", "được", "rồi", "vâng", "dạ"),
    "ko": ("네", "예", "돼요", "됩니다", "가능"),
    "zh": ("可以", "是", "能", "好", "行"),
    "en": (),
}


def _hhmm(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))


def _role(m: MemoryObject) -> str:
    return (m.speaker_role or "someone").lower()


@dataclass
class IngestResult:
    memory: MemoryObject | None
    alerts: list[dict] = field(default_factory=list)  # {"level": "red|amber|green", "text_en": ...}
    resolved: list[MemoryObject] = field(default_factory=list)
    verification_question_en: str = ""
    answer_en: str = ""  # when the utterance was a question MindBridge can answer
    explanation: list[str] = field(default_factory=list)


class MemoryEngine:
    def __init__(self, store: MemoryStore):
        self.store = store

    # ------------------------------------------------------------------ ingest
    def ingest(
        self,
        text_en: str,
        text_source: str,
        source_lang: str,
        speaker_role: str,
        text_listener: str = "",
        listener_lang: str = "",
    ) -> IngestResult:
        ex = extract(text_en, text_source, source_lang)
        res = IngestResult(memory=None, explanation=ex.explanation)

        if ex.kind == "question":
            res.answer_en = self.answer(text_en, text_source, source_lang) if (ex.subject or ex.action) else ""
            return res
        if ex.kind == "note" and not ex.subject:
            return res  # small talk is never stored — operational memory only

        m = MemoryObject(
            kind=ex.kind, text_en=text_en, text_source=text_source, source_lang=source_lang,
            speaker_role=speaker_role, subject=ex.subject, action=ex.action, action_family=ex.action_family,
            polarity=ex.polarity, condition=ex.condition, risk=ex.risk, hazards=ex.hazards,
            text_listener=text_listener, listener_lang=listener_lang,
            status="info" if ex.kind in ("outcome", "note") else "active",
        )

        # Conflicts are checked *before* storing, against what is already active.
        res.alerts += self._conflicts(m)
        if any(a["level"] == "red" for a in res.alerts):
            m.status = "held"  # not in force until a supervisor confirms

        if ex.kind == "outcome":
            res.resolved = self._resolve_with(m)
        if ex.kind in ("instruction", "exception") and ex.polarity == "forbid":
            for old in self._same_restriction(m):
                old.status = "superseded"
                self.store.update(old)

        m.needs_verification = ex.kind in ("instruction", "exception", "procedure") and (
            ex.polarity == "forbid" or ex.risk in ("high", "critical")
        )
        m.verified = "pending" if m.needs_verification else "n/a"
        self.store.add(m)
        if m.needs_verification:
            res.verification_question_en = self.verification_question(m)

        if m.kind == "issue":
            res.alerts.append({"level": "amber", "text_en": f"Issue logged for {m.subject or 'the line'}: {m.text_en}"})
        for r in res.resolved:
            res.alerts.append({"level": "green", "text_en": f"Cleared: {r.text_en}"})
        res.memory = m
        self.store.log_event("ingest", {"memory": m.to_dict(), "alerts": res.alerts})
        return res

    # --------------------------------------------------------------- conflicts
    def _conflicts(self, m: MemoryObject) -> list[dict]:
        alerts = []
        if not m.subject or not m.action_family:
            return alerts
        for old in self.store.active():
            if old.subject != m.subject:
                continue
            if (
                old.polarity == "forbid"
                and old.action_family == m.action_family
                and m.polarity == "require"
                and m.kind in ("instruction", "decision", "procedure")
            ):
                cond = f" ({old.condition})" if old.condition else ""
                alerts.append({
                    "level": "red",
                    "conflict_with": old.id,
                    "text_en": (
                        f"Conflict: at {_hhmm(old.created_at)} the {_role(old)} said not to {old.action} "
                        f"{old.subject}{cond}. That restriction is still active. Please confirm before acting."
                    ),
                })
            elif old.kind == "issue" and m.polarity == "require" and m.action_family == "start":
                alerts.append({
                    "level": "amber",
                    "conflict_with": old.id,
                    "text_en": f"Caution: {old.subject} has an open issue from {_hhmm(old.created_at)}: {old.text_en}",
                })
        return alerts

    def _same_restriction(self, m: MemoryObject) -> list[MemoryObject]:
        return [
            o for o in self.store.active()
            if o.subject == m.subject and o.polarity == "forbid" and o.action_family == m.action_family and m.subject
        ]

    # --------------------------------------------------------------- resolve
    def _resolve_with(self, outcome: MemoryObject) -> list[MemoryObject]:
        words = content_words(outcome.text_en)
        resolved = []
        for old in self.store.active():
            if old.kind not in ("instruction", "exception", "issue", "commitment"):
                continue
            target = content_words(old.text_en if old.kind in ("commitment", "issue") else (old.condition or old.text_en))
            overlap = words & target
            same_subject = bool(outcome.subject) and outcome.subject == old.subject
            # A restriction "until the valve is replaced" is cleared by "the valve was replaced".
            if (old.condition and len(overlap) >= 2) or (old.condition and overlap and same_subject):
                hit = True
            elif old.kind in ("issue", "commitment") and (same_subject or len(overlap) >= 2):
                hit = True
            elif same_subject and old.polarity == "forbid" and re.search(r"passed|test|working|normal|signed", outcome.text_en, re.I):
                hit = True
            else:
                hit = False
            if hit:
                old.status = "resolved"
                old.resolved_by = None  # set after outcome is stored
                self.store.update(old)
                resolved.append(old)
        return resolved

    # --------------------------------------------------------------- verify
    @staticmethod
    def verification_question(m: MemoryObject) -> str:
        subj = m.subject or "it"
        if m.subject and not any(ch.isdigit() for ch in m.subject):
            subj = f"the {m.subject.lower()}"
        if m.polarity == "forbid" and m.action:
            return f"Quick check: can we {m.action} {subj} now?"
        if m.action and m.subject:
            return f"Quick check: what do you need to do with {subj}?"
        return "Quick check: please repeat the instruction in your own words."

    def check_verification(self, memory_id: int, answer_en: str, answer_source: str, answer_lang: str) -> dict:
        m = self.store.get(memory_id)
        if m is None:
            return {"ok": False, "reason": "unknown memory"}
        native = answer_source.lower()
        says_no = bool(_NO_EN.search(answer_en)) or any(w in native for w in _NO_NATIVE.get(answer_lang, ()))
        says_yes = (bool(_YES_EN.search(answer_en)) or any(w in native for w in _YES_NATIVE.get(answer_lang, ()))) and not says_no
        if m.polarity == "forbid":
            ok = says_no
            reason = "answered that it must not happen yet" if ok else "answer suggests it is allowed — re-explain"
        else:
            want = content_words(f"{m.action} {m.subject}")
            got = content_words(answer_en) | {w for w in re.findall(r"\d+", answer_source)}
            ok = len(want & got) >= max(1, len(want) // 2) or says_yes
            reason = "read-back matches the instruction" if ok else "read-back misses key details — re-explain"
        m.verified = "confirmed" if ok else "failed"
        self.store.update(m)
        self.store.log_event("verify", {"memory_id": m.id, "answer_en": answer_en, "ok": ok})
        return {"ok": ok, "reason": reason, "memory": m.to_dict()}

    # --------------------------------------------------------------- recall
    def answer(self, question_en: str, question_source: str = "", lang: str = "en") -> str:
        ents = find_entities(question_en, question_source, lang)
        verb, fam, _ = find_action(question_en)
        mems = self.store.all()
        if re.search(r"\b(what changed|what happened|since yesterday|since this morning|handover|summary|update)\b", question_en, re.I) and not ents:
            return self.handover_en()
        if not ents:
            active = [m for m in mems if m.status == "active"]
            if not active:
                return "There are no active instructions or open issues right now."
            return "Active now: " + " ".join(f"{m.subject or ''} — {m.text_en}".strip(" —") for m in active[:4])
        subj = ents[0]
        about = [m for m in mems if m.subject == subj]
        if not about:
            return f"I have no record about {subj} yet."
        if fam:
            blockers = [m for m in about if m.status == "active" and m.polarity == "forbid" and m.action_family == fam]
            if blockers:
                b = blockers[0]
                ver = " The operator confirmed they understood." if b.verified == "confirmed" else ""
                cond = f" {b.condition[0].upper() + b.condition[1:]} — still pending." if b.condition else ""
                return (
                    f"Not yet. At {_hhmm(b.created_at)} the {_role(b)} instructed: \"{b.text_en}\"{ver}{cond}"
                )
            lifted = [m for m in about if m.status == "resolved" and m.polarity == "forbid" and m.action_family == fam]
            if lifted:
                b = lifted[0]
                return (
                    f"Yes. The restriction from {_hhmm(b.created_at)} (\"{b.text_en}\") was cleared at "
                    f"{_hhmm(b.updated_at)}. Follow normal procedure."
                )
            issues = [m for m in about if m.status == "active" and m.kind == "issue"]
            if issues:
                return f"There is no restriction, but there is an open issue from {_hhmm(issues[0].created_at)}: {issues[0].text_en}"
            return f"There is no active restriction on {subj}."
        lines = [f"{_hhmm(m.created_at)} {m.kind}: {m.text_en} [{m.status}]" for m in about[:5]]
        return f"Here is what I know about {subj}: " + " ".join(lines)

    # --------------------------------------------------------------- handover
    def handover_en(self) -> str:
        mems = self.store.all()
        act = [m for m in mems if m.status == "active"]
        restrictions = [m for m in act if m.polarity == "forbid"]
        issues = [m for m in act if m.kind == "issue"]
        commits = [m for m in act if m.kind == "commitment"]
        decisions = [m for m in act if m.kind in ("decision", "procedure") or (m.kind == "instruction" and m.polarity == "require")]
        cleared = [m for m in mems if m.status == "resolved"]
        out = ["Shift handover."]
        if restrictions:
            out.append(f"{len(restrictions)} active restriction(s): " + " ".join(f"{m.text_en}" for m in restrictions[:5]))
        if issues:
            out.append(f"{len(issues)} open issue(s): " + " ".join(m.text_en for m in issues[:5]))
        if commits:
            out.append("Outstanding commitments: " + " ".join(m.text_en for m in commits[:5]))
        if decisions:
            out.append("Decisions and instructions in force: " + " ".join(m.text_en for m in decisions[:5]))
        if cleared:
            out.append("Cleared this shift: " + " ".join(m.text_en for m in cleared[:5]))
        if len(out) == 1:
            out.append("Nothing open. All clear.")
        return " ".join(out)

    def handover_structured(self) -> dict:
        mems = self.store.all()
        act = [m for m in mems if m.status == "active"]
        return {
            "restrictions": [m.to_dict() for m in act if m.polarity == "forbid"],
            "issues": [m.to_dict() for m in act if m.kind == "issue"],
            "commitments": [m.to_dict() for m in act if m.kind == "commitment"],
            "decisions": [m.to_dict() for m in act if m.kind in ("decision", "procedure") or (m.kind == "instruction" and m.polarity == "require")],
            "cleared": [m.to_dict() for m in mems if m.status == "resolved"],
        }

    def safety_light(self) -> str:
        act = self.store.active()
        if any(m.polarity == "forbid" and m.verified in ("pending", "failed") for m in act):
            return "red"
        if any(m.polarity == "forbid" or m.kind == "issue" for m in act):
            return "amber"
        return "green"
