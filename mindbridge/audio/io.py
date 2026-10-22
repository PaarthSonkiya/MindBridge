"""Microphone capture and speaker playback (PortAudio via sounddevice).

Imported lazily so the rest of MindBridge (benchmarks, tests, file input) works
on machines without an audio stack.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import numpy as np

from mindbridge.audio.dsp import TARGET_SR, resample


def _sd():
    import sounddevice as sd  # noqa: PLC0415

    return sd


def _resolve_device(spec: str, kind: str) -> int | None:
    if not spec:
        return None
    if spec.isdigit():
        return int(spec)
    sd = _sd()
    for idx, dev in enumerate(sd.query_devices()):
        channels = dev["max_input_channels"] if kind == "input" else dev["max_output_channels"]
        if channels > 0 and spec.lower() in dev["name"].lower():
            return idx
    return None


def list_devices() -> list[dict]:
    try:
        sd = _sd()
        return [
            {
                "index": i,
                "name": d["name"],
                "inputs": d["max_input_channels"],
                "outputs": d["max_output_channels"],
                "default_sr": d["default_samplerate"],
            }
            for i, d in enumerate(sd.query_devices())
        ]
    except Exception as exc:  # pragma: no cover - depends on host audio
        return [{"error": str(exc)}]


class Recorder:
    """Push-to-talk recorder with optional VAD auto-endpointing.

    start() opens the mic; stop() returns 16 kHz mono float32 audio. If an
    endpoint detector is supplied, ``on_auto_stop`` fires after trailing silence.
    """

    def __init__(self, device: str = "", max_seconds: float = 25.0):
        self.device = device
        self.max_seconds = max_seconds
        self._chunks: list[np.ndarray] = []
        self._stream = None
        self._lock = threading.Lock()
        self._native_sr = TARGET_SR
        self.started_at = 0.0
        self.level_dbfs = -120.0

    @property
    def active(self) -> bool:
        return self._stream is not None

    def start(self, endpoint=None, silence_s: float = 0.9, on_auto_stop: Callable[[], None] | None = None):
        sd = _sd()
        dev = _resolve_device(self.device, "input")
        try:
            sd.check_input_settings(device=dev, samplerate=TARGET_SR, channels=1)
            self._native_sr = TARGET_SR
        except Exception:
            info = sd.query_devices(dev, "input")
            self._native_sr = int(info["default_samplerate"])
        self._chunks = []
        self.started_at = time.monotonic()
        fired = {"done": False}

        def cb(indata, frames, t, status):  # noqa: ARG001
            block = indata[:, 0].copy()
            with self._lock:
                self._chunks.append(block)
            rms = float(np.sqrt(np.mean(block**2))) if block.size else 0.0
            self.level_dbfs = 20 * np.log10(max(rms, 1e-6))
            if fired["done"]:
                return
            too_long = time.monotonic() - self.started_at > self.max_seconds
            ended = False
            if endpoint is not None:
                endpoint.accept(resample(block, self._native_sr))
                ended = endpoint.heard_speech and endpoint.trailing_silence_s() >= silence_s
            if ended or too_long:
                fired["done"] = True
                if on_auto_stop:
                    threading.Thread(target=on_auto_stop, daemon=True).start()

        self._stream = sd.InputStream(
            device=dev, channels=1, samplerate=self._native_sr, dtype="float32", blocksize=1024, callback=cb
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, np.float32)
            self._chunks = []
        return resample(audio, self._native_sr)


class Player:
    def __init__(self, device: str = ""):
        self.device = device
        self._lock = threading.Lock()

    def play(self, audio: np.ndarray, sr: int, block: bool = False) -> None:
        def run():
            with self._lock:
                try:
                    sd = _sd()
                    sd.play(audio, sr, device=_resolve_device(self.device, "output"))
                    sd.wait()
                except Exception as exc:  # pragma: no cover
                    print(f"[audio] playback failed: {exc}")

        if block:
            run()
        else:
            threading.Thread(target=run, daemon=True).start()
