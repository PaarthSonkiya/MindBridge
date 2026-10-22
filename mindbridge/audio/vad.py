"""Silero voice-activity detection (via sherpa-onnx, CPU, ~2 MB model).

Used to (a) trim leading/trailing noise before ASR and (b) auto-stop recording
when the speaker goes quiet, so a worker can tap once and talk hands-free.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from mindbridge.audio.dsp import TARGET_SR


class Vad:
    def __init__(self, model_path: Path, threshold: float = 0.5, min_silence_s: float = 0.3):
        import sherpa_onnx as so

        self._so = so
        cfg = so.VadModelConfig()
        cfg.silero_vad.model = str(model_path)
        cfg.silero_vad.threshold = threshold
        cfg.silero_vad.min_silence_duration = min_silence_s
        cfg.silero_vad.min_speech_duration = 0.15
        cfg.silero_vad.window_size = 512
        cfg.sample_rate = TARGET_SR
        cfg.num_threads = 1
        self._cfg = cfg
        self.window = 512

    def speech_segments(self, audio: np.ndarray) -> list[tuple[int, int]]:
        """Return [(start_sample, end_sample)] of detected speech."""
        vad = self._so.VoiceActivityDetector(self._cfg, buffer_size_in_seconds=60)
        segs: list[tuple[int, int]] = []
        for i in range(0, len(audio) - self.window + 1, self.window):
            vad.accept_waveform(audio[i : i + self.window])
            while not vad.empty():
                s = vad.front
                segs.append((s.start, s.start + len(s.samples)))
                vad.pop()
        vad.flush()
        while not vad.empty():
            s = vad.front
            segs.append((s.start, s.start + len(s.samples)))
            vad.pop()
        return segs

    def trim(self, audio: np.ndarray, margin_s: float = 0.25) -> np.ndarray:
        segs = self.speech_segments(audio)
        if not segs:
            return audio
        m = int(margin_s * TARGET_SR)
        start = max(0, segs[0][0] - m)
        end = min(len(audio), segs[-1][1] + m)
        return audio[start:end]

    def streaming(self) -> StreamingEndpoint:
        return StreamingEndpoint(self)


class StreamingEndpoint:
    """Feeds live microphone blocks; reports when speech started and then stopped."""

    def __init__(self, vad: Vad):
        self._vad = vad._so.VoiceActivityDetector(vad._cfg, buffer_size_in_seconds=60)
        self._buf = np.zeros(0, dtype=np.float32)
        self.window = vad.window
        self.heard_speech = False
        self.silence_samples = 0

    def accept(self, block: np.ndarray) -> None:
        self._buf = np.concatenate([self._buf, block.astype(np.float32)])
        while len(self._buf) >= self.window:
            frame, self._buf = self._buf[: self.window], self._buf[self.window :]
            self._vad.accept_waveform(frame)
            if self._vad.is_speech_detected():
                self.heard_speech = True
                self.silence_samples = 0
            else:
                self.silence_samples += self.window

    def trailing_silence_s(self) -> float:
        return self.silence_samples / TARGET_SR
