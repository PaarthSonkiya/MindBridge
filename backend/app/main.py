"""MindBridge backend — FastAPI application exposing the Understanding Engine."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.engine.pipeline import UnderstandingEngine
from app.memory.context_store import ContextStore
from app.models.schemas import (
    HandoverRequest,
    HandoverResponse,
    HealthResponse,
    ProcessRequest,
    ProcessResponse,
    VerifyRequest,
    VerifyResponse,
)

settings = get_settings()
store = ContextStore()
engine = UnderstandingEngine(settings, store)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "MindBridge translates *understanding*, not just language. This API powers "
        "the Edge AI pipeline: intent recognition, risk intelligence, translation, "
        "expertise adaptation, and the Understanding Score™ comprehension check."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.version,
        engine="claude" if settings.llm_enabled else "offline-heuristic",
        llm_enabled=settings.llm_enabled,
    )


@app.post("/api/process", response_model=ProcessResponse, tags=["engine"])
def process(req: ProcessRequest) -> ProcessResponse:
    """Run a message through the full understanding pipeline."""
    return engine.process(req)


@app.post("/api/verify", response_model=VerifyResponse, tags=["engine"])
def verify(req: VerifyRequest) -> VerifyResponse:
    """Score how well a listener understood an instruction from their read-back."""
    return engine.verify(req)


@app.post("/api/handover", response_model=HandoverResponse, tags=["engine"])
def handover(req: HandoverRequest) -> HandoverResponse:
    """Generate an AI shift-handover report for a session."""
    return engine.handover(req.session_id)


@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "tagline": "Translating Understanding, Not Just Language",
    }
