"""The Understanding Engine pipeline.

Orchestrates every stage of the Edge AI pipeline:

    Speech/Text → Intent → Risk → Translation → Expertise Adaptation
                → Understanding Verification → Context Memory

Each public method works fully offline with deterministic heuristics and
transparently upgrades to Claude-powered reasoning when an API key is present.
"""

from __future__ import annotations

from app.config import Settings
from app.engine.expertise import adapt_for_expertise
from app.engine.intent import classify_intent
from app.engine.risk import assess_risk
from app.engine.translator import translate_offline
from app.engine.understanding import build_follow_up, score_understanding
from app.llm.client import ClaudeClient, LLMUnavailable
from app.memory.context_store import ContextStore, Turn, now_iso
from app.models.schemas import (
    HandoverResponse,
    Intent,
    ProcessRequest,
    ProcessResponse,
    RiskAssessment,
    RiskLevel,
    UnderstandingFactor,
    VerifyRequest,
    VerifyResponse,
)


class UnderstandingEngine:
    def __init__(self, settings: Settings, store: ContextStore | None = None) -> None:
        self.settings = settings
        self.store = store or ContextStore()
        self.llm = ClaudeClient(settings)

    # ------------------------------------------------------------------ #
    # Stage orchestration
    # ------------------------------------------------------------------ #
    def process(self, req: ProcessRequest) -> ProcessResponse:
        intent = classify_intent(req.text)
        risk = assess_risk(req.text)

        translation, engine = self._translate(req, intent, risk)
        adapted, key_points = adapt_for_expertise(req.text, req.listener_expertise)

        requires_readback = risk.requires_confirmation or intent in {
            Intent.INSTRUCTION,
            Intent.EMERGENCY,
            Intent.WARNING,
        }

        self.store.add_turn(
            req.session_id,
            Turn(
                timestamp=now_iso(),
                speaker=req.speaker,
                text=req.text,
                intent=intent,
                risk_level=risk.level,
                hazards=risk.hazards,
            ),
        )

        return ProcessResponse(
            session_id=req.session_id,
            original_text=req.text,
            translation=translation,
            intent=intent,
            risk=risk,
            adapted_message=adapted,
            key_points=key_points,
            requires_readback=requires_readback,
            engine=engine,
        )

    def verify(self, req: VerifyRequest) -> VerifyResponse:
        if self.llm.enabled:
            try:
                return self._verify_with_claude(req)
            except (LLMUnavailable, Exception):  # noqa: BLE001 - graceful degradation
                pass

        score, understood, factors, missing = score_understanding(
            req.original_text, req.readback_text, self.settings.understanding_threshold
        )
        follow_up = build_follow_up(understood, missing, req.readback_text)

        # Annotate the most recent matching turn with its understanding score.
        session = self.store.get(req.session_id)
        if session.turns:
            session.turns[-1].understanding_score = score

        return VerifyResponse(
            session_id=req.session_id,
            understanding_score=score,
            understood=understood,
            factors=factors,
            missing_points=missing,
            follow_up=follow_up,
            engine="offline-heuristic",
        )

    def handover(self, session_id: str) -> HandoverResponse:
        session = self.store.get(session_id)
        completed: list[str] = []
        pending: list[str] = []
        safety: list[str] = []

        for turn in session.turns:
            if turn.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
                safety.append(f"[{turn.risk_level.value.upper()}] {turn.text}")
            if turn.intent == Intent.INSTRUCTION:
                verified = (
                    turn.understanding_score is not None
                    and turn.understanding_score >= self.settings.understanding_threshold
                )
                (completed if verified else pending).append(turn.text)
            elif turn.intent in {Intent.ESCALATION, Intent.EMERGENCY}:
                pending.append(f"({turn.intent.value}) {turn.text}")

        equipment = self.store.equipment_referenced(session_id)
        summary = self._handover_summary(session_id, completed, pending, safety, equipment)

        return HandoverResponse(
            session_id=session_id,
            generated_at=now_iso(),
            summary=summary,
            completed_tasks=completed,
            pending_issues=pending,
            safety_observations=safety,
            equipment_referenced=equipment,
            engine="claude" if self.llm.enabled else "offline-heuristic",
        )

    # ------------------------------------------------------------------ #
    # Claude-backed paths (used only when a key is configured)
    # ------------------------------------------------------------------ #
    def _translate(
        self, req: ProcessRequest, intent: Intent, risk: RiskAssessment
    ) -> tuple[str, str]:
        if self.llm.enabled and req.source_lang != req.target_lang:
            try:
                data = self.llm.complete_json(
                    system=(
                        "You are MindBridge, an industrial communication engine. "
                        "Translate the message faithfully, preserving every safety-"
                        "critical detail. Reply as JSON: {\"translation\": string}."
                    ),
                    user=(
                        f"Translate from {req.source_lang.value} to {req.target_lang.value}.\n"
                        f"Message: {req.text}"
                    ),
                    max_tokens=512,
                )
                return str(data["translation"]).strip(), "claude"
            except (LLMUnavailable, Exception):  # noqa: BLE001
                pass
        return translate_offline(req.text, req.source_lang, req.target_lang), "offline-heuristic"

    def _verify_with_claude(self, req: VerifyRequest) -> VerifyResponse:
        data = self.llm.complete_json(
            system=(
                "You are MindBridge's comprehension verifier. Compare a worker's "
                "read-back to an instruction and estimate whether they understood. "
                "Reply ONLY as JSON with this shape: {\"understanding_score\": int 0-100, "
                "\"missing_points\": [string], \"factors\": [{\"name\": string, "
                "\"score\": int, \"detail\": string}], \"follow_up\": string}."
            ),
            user=f"Instruction: {req.original_text}\nRead-back: {req.readback_text}",
            max_tokens=800,
        )
        score = int(data["understanding_score"])
        understood = score >= self.settings.understanding_threshold
        factors = [UnderstandingFactor(**f) for f in data.get("factors", [])]
        return VerifyResponse(
            session_id=req.session_id,
            understanding_score=score,
            understood=understood,
            factors=factors,
            missing_points=list(data.get("missing_points", [])),
            follow_up=str(data.get("follow_up", "")),
            engine="claude",
        )

    def _handover_summary(
        self,
        session_id: str,
        completed: list[str],
        pending: list[str],
        safety: list[str],
        equipment: list[str],
    ) -> str:
        if self.llm.enabled:
            try:
                transcript = self.store.recent_context(session_id, limit=50)
                data = self.llm.complete_json(
                    system=(
                        "You are MindBridge's shift-handover assistant. Write a concise, "
                        "professional handover summary (3-4 sentences) for the incoming "
                        "shift. Reply as JSON: {\"summary\": string}."
                    ),
                    user=transcript or "No conversation recorded.",
                    max_tokens=400,
                )
                return str(data["summary"]).strip()
            except (LLMUnavailable, Exception):  # noqa: BLE001
                pass

        n = len(completed) + len(pending)
        return (
            f"Shift handover for session '{session_id}': {len(completed)} task(s) verified "
            f"complete, {len(pending)} pending, {len(safety)} safety-critical item(s) logged "
            f"across {n} instruction(s). Review pending issues and safety observations before "
            f"taking over the line."
        )
