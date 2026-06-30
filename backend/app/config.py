"""Runtime configuration for the MindBridge backend.

Configuration is environment-driven so the same image can run on a developer
laptop, in CI, or on a Snapdragon-powered edge device. Every setting has a
sensible default so the service boots with zero configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Immutable application settings resolved once at startup."""

    app_name: str = "MindBridge Understanding Engine"
    version: str = "0.1.0"

    # When an Anthropic API key is present the engine upgrades from the
    # deterministic on-device heuristics to Claude-powered reasoning.
    anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(
        default_factory=lambda: os.getenv("MINDBRIDGE_MODEL", "claude-opus-4-8")
    )

    # Forces the offline heuristic engine even if a key is configured. Useful
    # for deterministic tests and air-gapped edge deployments.
    force_offline: bool = field(
        default_factory=lambda: _env_bool("MINDBRIDGE_FORCE_OFFLINE", False)
    )

    # Understanding Score below this threshold triggers an automatic
    # clarification / re-explanation loop.
    understanding_threshold: int = field(
        default_factory=lambda: int(os.getenv("MINDBRIDGE_UNDERSTANDING_THRESHOLD", "70"))
    )

    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.getenv(
                "MINDBRIDGE_CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        )
    )

    @property
    def llm_enabled(self) -> bool:
        """True when Claude-backed reasoning should be used."""
        return bool(self.anthropic_api_key) and not self.force_offline


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
