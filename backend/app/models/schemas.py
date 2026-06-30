"""Pydantic schemas — the public contract of the Understanding Engine."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    EN = "en"
    VI = "vi"


class Expertise(str, Enum):
    """Listener expertise levels the engine adapts explanations to."""

    ENGINEER = "engineer"
    TECHNICIAN = "technician"
    OPERATOR = "operator"
    TRAINEE = "trainee"


class Intent(str, Enum):
    INSTRUCTION = "instruction"
    WARNING = "warning"
    QUESTION = "question"
    CONFIRMATION = "confirmation"
    EMERGENCY = "emergency"
    APPROVAL = "approval"
    ESCALATION = "escalation"
    STATEMENT = "statement"


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAssessment(BaseModel):
    level: RiskLevel = RiskLevel.NONE
    requires_confirmation: bool = False
    hazards: list[str] = Field(default_factory=list)
    rationale: str = ""


class ProcessRequest(BaseModel):
    """A message entering the pipeline."""

    text: str = Field(..., min_length=1, description="Raw message text from the speaker.")
    source_lang: Language = Language.EN
    target_lang: Language = Language.VI
    listener_expertise: Expertise = Expertise.OPERATOR
    session_id: str = Field(default="default", description="Conversation / shift session.")
    speaker: str = Field(default="supervisor")


class ProcessResponse(BaseModel):
    """The fully analysed and adapted message."""

    session_id: str
    original_text: str
    translation: str
    intent: Intent
    risk: RiskAssessment
    adapted_message: str
    key_points: list[str] = Field(default_factory=list)
    requires_readback: bool = False
    engine: str = Field(description="'claude' or 'offline-heuristic'.")


class VerifyRequest(BaseModel):
    """A listener's read-back, checked against the original instruction."""

    session_id: str = "default"
    original_text: str
    readback_text: str
    listener_expertise: Expertise = Expertise.OPERATOR


class UnderstandingFactor(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    detail: str = ""


class VerifyResponse(BaseModel):
    session_id: str
    understanding_score: int = Field(ge=0, le=100)
    understood: bool
    factors: list[UnderstandingFactor]
    missing_points: list[str] = Field(default_factory=list)
    follow_up: str = ""
    engine: str


class HandoverRequest(BaseModel):
    session_id: str = "default"


class HandoverResponse(BaseModel):
    session_id: str
    generated_at: str
    summary: str
    completed_tasks: list[str] = Field(default_factory=list)
    pending_issues: list[str] = Field(default_factory=list)
    safety_observations: list[str] = Field(default_factory=list)
    equipment_referenced: list[str] = Field(default_factory=list)
    engine: str


class HealthResponse(BaseModel):
    status: str
    version: str
    engine: str
    llm_enabled: bool
