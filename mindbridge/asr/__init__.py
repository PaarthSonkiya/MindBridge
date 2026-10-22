"""Speech recognition backends. ``load_asr`` picks the NPU when it can."""

from __future__ import annotations

import logging

from mindbridge.asr.base import AsrEngine, AsrResult
from mindbridge.config import AppConfig

log = logging.getLogger("mindbridge.asr")

__all__ = ["AsrEngine", "AsrResult", "load_asr"]


def load_asr(cfg: AppConfig) -> AsrEngine:
    from mindbridge.ort_qnn import qnn_available

    backend = cfg.asr.backend
    qnn_dir = cfg.models_path / cfg.asr.qnn_model_dir
    errors: list[str] = []
    if backend in ("auto", "qnn"):
        ok, why = qnn_available()
        if ok and qnn_dir.exists():
            try:
                from mindbridge.asr.whisper_qnn import WhisperQnn

                eng = WhisperQnn(qnn_dir, "qnn", cfg.asr.max_tokens, cfg.asr.threads)
                log.info("ASR on NPU: %s", why)
                return eng
            except Exception as exc:  # noqa: BLE001
                errors.append(f"QNN load failed: {exc}")
        else:
            errors.append(f"QNN unavailable: {why if not ok else 'model dir missing: ' + str(qnn_dir)}")
        if backend == "qnn":
            raise RuntimeError("; ".join(errors))
    from mindbridge.asr.whisper_sherpa import WhisperSherpa

    eng = WhisperSherpa(cfg.models_path / cfg.asr.cpu_model_dir, cfg.asr.cpu_model_prefix, cfg.asr.threads)
    if errors:
        log.warning("ASR falling back to CPU (%s)", "; ".join(errors))
    eng.fallback_reason = "; ".join(errors)  # type: ignore[attr-defined]
    return eng
