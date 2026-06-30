"""Thin Claude client used by the engine when an API key is configured.

The client is intentionally optional: the rest of the engine degrades to a
deterministic on-device heuristic when Claude is unavailable, which keeps the
demo runnable offline and on edge hardware.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import Settings


class LLMUnavailable(RuntimeError):
    """Raised when a Claude call is attempted but cannot be served."""


class ClaudeClient:
    """Lazily-initialised wrapper around the Anthropic SDK."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        return self._settings.llm_enabled

    def _ensure_client(self) -> Any:
        if not self.enabled:
            raise LLMUnavailable("Claude is not enabled (no API key or forced offline).")
        if self._client is None:
            try:
                import anthropic  # imported lazily so the dep stays optional
            except ImportError as exc:  # pragma: no cover - import guard
                raise LLMUnavailable(
                    "The 'anthropic' package is not installed. Run `pip install anthropic`."
                ) from exc
            self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    def complete_json(self, system: str, user: str, max_tokens: int = 1024) -> dict:
        """Call Claude and parse a single JSON object from the reply."""
        client = self._ensure_client()
        message = client.messages.create(
            model=self._settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in message.content if block.type == "text")
        return _extract_json(text)


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply, tolerating prose."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMUnavailable(f"No JSON object found in model reply: {text!r}")
    return json.loads(text[start : end + 1])
