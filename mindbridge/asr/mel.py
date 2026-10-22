"""Whisper log-mel features in pure numpy (no torch / transformers on device).

Numerically matches ``transformers.WhisperFeatureExtractor`` (verified in
tests/test_mel.py): 16 kHz audio, 25 ms Hann window, 10 ms hop, Slaney mel
filterbank, log10, dynamic-range clamp of 8, then (x + 4) / 4.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

SAMPLE_RATE = 16000
N_FFT = 400
HOP = 160
CHUNK_SECONDS = 30
N_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS  # 480000
N_FRAMES = N_SAMPLES // HOP  # 3000


def _hz_to_mel(f: np.ndarray) -> np.ndarray:
    f = np.asarray(f, dtype=np.float64)
    f_sp = 200.0 / 3
    mels = f / f_sp
    min_log_hz = 1000.0
    min_log_mel = min_log_hz / f_sp
    logstep = np.log(6.4) / 27.0
    return np.where(f >= min_log_hz, min_log_mel + np.log(np.maximum(f, 1e-10) / min_log_hz) / logstep, mels)


def _mel_to_hz(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float64)
    f_sp = 200.0 / 3
    freqs = f_sp * m
    min_log_hz = 1000.0
    min_log_mel = min_log_hz / f_sp
    logstep = np.log(6.4) / 27.0
    return np.where(m >= min_log_mel, min_log_hz * np.exp(logstep * (m - min_log_mel)), freqs)


@lru_cache(maxsize=4)
def mel_filters(n_mels: int = 80) -> np.ndarray:
    """Slaney-normalised mel filterbank, shape (n_freqs=201, n_mels)."""
    fft_freqs = np.linspace(0, SAMPLE_RATE / 2, 1 + N_FFT // 2)
    mel_pts = np.linspace(_hz_to_mel(0.0), _hz_to_mel(SAMPLE_RATE / 2), n_mels + 2)
    hz_pts = _mel_to_hz(mel_pts)
    fdiff = np.diff(hz_pts)
    ramps = hz_pts[:, None] - fft_freqs[None, :]
    lower = -ramps[:-2] / fdiff[:-1, None]
    upper = ramps[2:] / fdiff[1:, None]
    weights = np.maximum(0.0, np.minimum(lower, upper))
    enorm = 2.0 / (hz_pts[2 : n_mels + 2] - hz_pts[:n_mels])
    weights *= enorm[:, None]
    return weights.T.astype(np.float64)


@lru_cache(maxsize=1)
def _window() -> np.ndarray:
    n = np.arange(N_FFT)
    return 0.5 - 0.5 * np.cos(2 * np.pi * n / N_FFT)  # periodic Hann


def log_mel(audio: np.ndarray, n_mels: int = 80) -> np.ndarray:
    """Return float32 features of shape (1, n_mels, 3000) for a ≤30 s clip."""
    audio = np.asarray(audio, dtype=np.float32)[:N_SAMPLES]
    if audio.shape[0] < N_SAMPLES:
        audio = np.pad(audio, (0, N_SAMPLES - audio.shape[0]))
    x = np.pad(audio.astype(np.float64), (N_FFT // 2, N_FFT // 2), mode="reflect")
    n_frames = 1 + (len(x) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = x[idx] * _window()[None, :]
    spec = np.abs(np.fft.rfft(frames, n=N_FFT, axis=1)) ** 2  # (frames, 201)
    mel = spec @ mel_filters(n_mels)  # (frames, n_mels)
    log_spec = np.log10(np.maximum(mel, 1e-10)).T  # (n_mels, frames)
    log_spec = log_spec[:, :-1]
    log_spec = np.maximum(log_spec, log_spec.max() - 8.0)
    log_spec = (log_spec + 4.0) / 4.0
    return log_spec[None, :, :N_FRAMES].astype(np.float32)
