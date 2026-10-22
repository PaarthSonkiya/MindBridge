from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class AsrResult:
    text: str
    language: str
    backend: str
    timings_ms: dict[str, float] = field(default_factory=dict)
    num_tokens: int = 0


class AsrEngine:
    name = "base"
    compute_unit = "cpu"

    def transcribe(self, audio: np.ndarray, language: str | None, candidates: list[str] | None = None) -> AsrResult:
        """audio: 16 kHz mono float32. language=None → detect among ``candidates``."""
        raise NotImplementedError

    def model_files(self) -> list[str]:
        return []
