"""Small, dependency-light audio helpers (numpy + scipy)."""

from __future__ import annotations

import io
import wave

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt

TARGET_SR = 16000


def to_mono_float32(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float32) / 2147483648.0
    return audio.astype(np.float32, copy=False)


def resample(audio: np.ndarray, sr: int, target_sr: int = TARGET_SR) -> np.ndarray:
    if sr == target_sr:
        return audio
    g = np.gcd(sr, target_sr)
    return resample_poly(audio, target_sr // g, sr // g).astype(np.float32)


_HP_SOS = butter(2, 80, btype="highpass", fs=TARGET_SR, output="sos")


def highpass(audio: np.ndarray) -> np.ndarray:
    """Remove rumble from fans, motors and handling noise below 80 Hz."""
    if audio.size < 32:
        return audio
    return sosfilt(_HP_SOS, audio).astype(np.float32)


def normalize(audio: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = float(np.max(np.abs(audio))) if audio.size else 0.0
    if m < 1e-4:
        return audio
    return (audio * (peak / m)).astype(np.float32)


def pad_tail(audio: np.ndarray, seconds: float = 0.5, sr: int = TARGET_SR) -> np.ndarray:
    """Whisper tends to drop the last word when speech ends abruptly; add silence."""
    return np.concatenate([audio, np.zeros(int(seconds * sr), dtype=np.float32)])


def rms_dbfs(audio: np.ndarray) -> float:
    if audio.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    return 20.0 * np.log10(max(rms, 1e-6))


def prepare_for_asr(audio: np.ndarray, sr: int) -> np.ndarray:
    audio = resample(to_mono_float32(audio), sr)
    audio = highpass(audio)
    audio = normalize(audio)
    return pad_tail(audio)


def wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def read_wav_bytes(data: bytes) -> tuple[np.ndarray, int]:
    import soundfile as sf

    audio, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
    return to_mono_float32(audio), int(sr)
