"""Runtime configuration.

Defaults live in ``config/mindbridge.toml``. Any key can be overridden with an
environment variable ``MINDBRIDGE_<SECTION>_<KEY>`` (e.g. ``MINDBRIDGE_ASR_BACKEND=cpu``).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _default_config_path() -> Path:
    return Path(os.environ.get("MINDBRIDGE_CONFIG", REPO_ROOT / "config" / "mindbridge.toml"))


@dataclass
class AsrConfig:
    backend: str = "auto"  # auto | qnn | cpu
    qnn_model_dir: str = "asr/whisper-large-v3-turbo-quantized-qcs6490"
    cpu_model_dir: str = "asr/ct2-whisper-small"
    max_tokens: int = 120
    threads: int = 4


@dataclass
class MtConfig:
    en_vi_model_dir: str = "mt/envit5-translation-ct2-int8"  # "" = use NLLB for English ⇄ Vietnamese too
    en_vi_beam_size: int = 1
    model_dir: str = "mt/nllb-200-distilled-1.3B-ct2-int8"
    beam_size: int = 2
    threads: int = 4
    max_decoding_length: int = 200


@dataclass
class TtsConfig:
    enabled: bool = True
    threads: int = 2
    speed: float = 1.0


@dataclass
class AudioConfig:
    input_device: str = ""  # sounddevice name/index; "" = system default
    output_device: str = ""
    sample_rate: int = 16000
    vad_endpoint_silence_s: float = 0.9  # auto-stop after this much trailing silence
    max_utterance_s: float = 25.0


@dataclass
class AppConfig:
    models_dir: str = "models"
    data_dir: str = "data"
    default_pair: str = "vi-en"
    host: str = "127.0.0.1"
    port: int = 8765
    strict_offline: bool = True  # block every non-loopback socket at runtime
    asr: AsrConfig = field(default_factory=AsrConfig)
    mt: MtConfig = field(default_factory=MtConfig)
    tts: TtsConfig = field(default_factory=TtsConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)

    # ---- resolved paths -------------------------------------------------
    @property
    def models_path(self) -> Path:
        p = Path(os.environ.get("MINDBRIDGE_MODELS_DIR", self.models_dir))
        return p if p.is_absolute() else REPO_ROOT / p

    @property
    def data_path(self) -> Path:
        p = Path(os.environ.get("MINDBRIDGE_DATA_DIR", self.data_dir))
        p = p if p.is_absolute() else REPO_ROOT / p
        p.mkdir(parents=True, exist_ok=True)
        return p


def _coerce(value: str, current: object) -> object:
    if isinstance(current, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(value)
    if isinstance(current, float):
        return float(value)
    return value


def _apply(obj: object, data: dict, prefix: str) -> None:
    for key, current in vars(obj).items():
        env_key = f"{prefix}{key}".upper()
        if hasattr(current, "__dataclass_fields__"):
            _apply(current, data.get(key, {}) or {}, f"{prefix}{key}_")
            continue
        if key in data:
            setattr(obj, key, data[key])
        if env_key in os.environ:
            setattr(obj, key, _coerce(os.environ[env_key], getattr(obj, key)))


def load_config(path: str | os.PathLike | None = None) -> AppConfig:
    cfg = AppConfig()
    cfg_path = Path(path) if path else _default_config_path()
    data: dict = {}
    if cfg_path.exists():
        with open(cfg_path, "rb") as fh:
            data = tomllib.load(fh)
    app_section = {k: v for k, v in data.items() if not isinstance(v, dict)}
    _apply(cfg, {**app_section, **{k: v for k, v in data.items() if isinstance(v, dict)}}, "MINDBRIDGE_")
    return cfg
