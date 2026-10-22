"""The MindBridge pipeline: speech → text → translation → speech, plus memory.

    mic ─▶ high-pass + VAD trim ─▶ Whisper (NPU) ─▶ NLLB (CPU) ─▶ VITS TTS (CPU) ─▶ speaker
                                          │
                                          └──▶ English pivot ─▶ Operational Memory (SQLite)

Every stage is timed; ``Turn.timings_ms`` is what the UI and benchmark logs show.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

import numpy as np

from mindbridge import languages as L
from mindbridge.asr import load_asr
from mindbridge.audio import dsp
from mindbridge.config import REPO_ROOT, AppConfig
from mindbridge.memory import MemoryEngine, MemoryStore
from mindbridge.metrics import files_size_mb
from mindbridge.mt import NllbTranslator
from mindbridge.mt.text import clean_asr
from mindbridge.tts import Tts

log = logging.getLogger("mindbridge.pipeline")


@dataclass
class Turn:
    id: str
    mode: str  # talk | ask | verify | text
    speaker_role: str
    speaker_lang: str
    listener_lang: str
    source_text: str = ""
    translation: str = ""
    english: str = ""
    asr_backend: str = ""
    audio_seconds: float = 0.0
    timings_ms: dict[str, float] = field(default_factory=dict)
    tts_sample_rate: int = 0
    created_at: float = field(default_factory=time.time)
    tts_audio: np.ndarray | None = None
    memory: dict | None = None
    alerts: list[dict] = field(default_factory=list)
    verification: dict | None = None  # {"memory_id", "question_en", "question", "lang"}
    answer: str = ""
    answer_en: str = ""
    explanation: list[str] = field(default_factory=list)

    def public(self) -> dict:
        d = asdict(self)
        d.pop("tts_audio", None)
        d["timings_ms"] = {k: round(v, 1) for k, v in self.timings_ms.items()}
        return d


class MindBridge:
    def __init__(self, cfg: AppConfig, load_tts: bool = True, load_memory: bool = True):
        self.cfg = cfg
        self.load_ms: dict[str, float] = {}
        mp = cfg.models_path

        t = time.perf_counter()
        self.vad = None
        vad_path = mp / "vad" / "silero_vad.onnx"
        if vad_path.exists():
            from mindbridge.audio.vad import Vad

            self.vad = Vad(vad_path)
        self.load_ms["vad"] = (time.perf_counter() - t) * 1e3

        t = time.perf_counter()
        self.asr = load_asr(cfg)
        self.load_ms["asr"] = (time.perf_counter() - t) * 1e3

        t = time.perf_counter()
        self.mt = NllbTranslator(
            mp / cfg.mt.model_dir,
            beam_size=cfg.mt.beam_size,
            threads=cfg.mt.threads,
            max_decoding_length=cfg.mt.max_decoding_length,
            phrasebook=REPO_ROOT / "config" / "phrasebook.json",
        )
        self.load_ms["mt"] = (time.perf_counter() - t) * 1e3

        self.tts = Tts(mp / "tts", cfg.tts.threads, cfg.tts.speed) if (load_tts and cfg.tts.enabled) else None
        if self.tts:
            t = time.perf_counter()
            a, b = cfg.default_pair.split("-")
            self.tts.preload([a, b])
            self.load_ms["tts"] = (time.perf_counter() - t) * 1e3

        self.memory = MemoryEngine(MemoryStore(cfg.data_path / "memory.db")) if load_memory else None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ stages
    def transcribe(self, audio: np.ndarray, sr: int, lang: str | None, candidates: list[str] | None = None):
        timings: dict[str, float] = {}
        t0 = time.perf_counter()
        x = dsp.prepare_for_asr(audio, sr)
        if self.vad is not None:
            x = dsp.pad_tail(self.vad.trim(x))
        timings["preprocess"] = (time.perf_counter() - t0) * 1e3
        t1 = time.perf_counter()
        res = self.asr.transcribe(x, lang, candidates)
        timings["asr"] = (time.perf_counter() - t1) * 1e3
        for k, v in res.timings_ms.items():
            timings[f"asr.{k}"] = v
        res.text = clean_asr(res.text, res.language)
        return res, timings, len(x) / dsp.TARGET_SR

    def translate(self, text: str, src: str, tgt: str):
        return self.mt.translate(text, src, tgt)

    def speak(self, text: str, lang: str):
        if not self.tts or not text.strip() or not self.tts.available(lang):
            return None
        return self.tts.synthesize(text, lang)

    # ------------------------------------------------------------------ turns
    def talk(
        self,
        audio: np.ndarray | None,
        sr: int,
        speaker_lang: str | None,
        listener_lang: str,
        speaker_role: str = "",
        text: str | None = None,
        synthesize: bool = True,
        remember: bool = True,
    ) -> Turn:
        """One conversational turn: what the speaker said, in the listener's language."""
        t_start = time.perf_counter()
        turn = Turn(uuid.uuid4().hex[:10], "talk" if text is None else "text", speaker_role, speaker_lang or "", listener_lang)
        if text is None:
            pair = [speaker_lang] if speaker_lang else None
            res, timings, secs = self.transcribe(audio, sr, speaker_lang, candidates=pair)
            turn.source_text, turn.speaker_lang, turn.asr_backend = res.text, res.language, res.backend
            turn.audio_seconds = secs
            turn.timings_ms.update(timings)
        else:
            turn.source_text = text.strip()
        if not turn.source_text:
            turn.timings_ms["total"] = (time.perf_counter() - t_start) * 1e3
            return turn

        mt = self.translate(turn.source_text, turn.speaker_lang, listener_lang)
        turn.translation = mt.text
        turn.timings_ms["mt"] = mt.timings_ms["mt"]

        if synthesize:
            out = self.speak(turn.translation, listener_lang)
            if out is not None:
                turn.tts_audio, turn.tts_sample_rate = out.audio, out.sample_rate
                turn.timings_ms["tts"] = out.ms
        turn.timings_ms["total"] = (time.perf_counter() - t_start) * 1e3
        turn.timings_ms["speech_to_translation"] = turn.timings_ms.get("asr", 0) + turn.timings_ms.get("preprocess", 0) + turn.timings_ms["mt"]

        if remember and self.memory is not None:
            self.remember(turn)
        return turn

    def english_of(self, text: str, lang: str, translation: str = "", translation_lang: str = "") -> str:
        if lang == "en":
            return text
        if translation_lang == "en":
            return translation
        return self.translate(text, lang, "en").text

    def remember(self, turn: Turn) -> Turn:
        t0 = time.perf_counter()
        turn.english = self.english_of(turn.source_text, turn.speaker_lang, turn.translation, turn.listener_lang)
        res = self.memory.ingest(
            turn.english, turn.source_text, turn.speaker_lang, turn.speaker_role, turn.translation, turn.listener_lang
        )
        turn.explanation = res.explanation
        if res.memory is not None:
            turn.memory = res.memory.to_dict()
        for a in res.alerts:
            a = dict(a)
            a["text"] = {
                turn.listener_lang: self.translate(a["text_en"], "en", turn.listener_lang).text,
                turn.speaker_lang: self.translate(a["text_en"], "en", turn.speaker_lang).text,
            }
            turn.alerts.append(a)
        if res.verification_question_en and res.memory is not None:
            q = self.translate(res.verification_question_en, "en", turn.listener_lang).text
            turn.verification = {
                "memory_id": res.memory.id,
                "question_en": res.verification_question_en,
                "question": q,
                "lang": turn.listener_lang,
            }
        if res.answer_en:
            turn.answer_en = res.answer_en
            turn.answer = self.translate(res.answer_en, "en", turn.speaker_lang).text
        turn.timings_ms["memory"] = (time.perf_counter() - t0) * 1e3
        return turn

    def ask(self, audio: np.ndarray | None, sr: int, lang: str, text: str | None = None) -> Turn:
        """A question to MindBridge itself ("Can we restart Machine 4?"), answered in ``lang``."""
        t0 = time.perf_counter()
        turn = Turn(uuid.uuid4().hex[:10], "ask", "asker", lang, lang)
        if text is None:
            res, timings, secs = self.transcribe(audio, sr, lang, [lang])
            turn.source_text, turn.asr_backend, turn.audio_seconds = res.text, res.backend, secs
            turn.timings_ms.update(timings)
        else:
            turn.source_text = text
        turn.english = self.english_of(turn.source_text, lang)
        turn.answer_en = self.memory.answer(turn.english, turn.source_text, lang)
        turn.answer = self.translate(turn.answer_en, "en", lang).text
        out = self.speak(turn.answer, lang)
        if out is not None:
            turn.tts_audio, turn.tts_sample_rate = out.audio, out.sample_rate
            turn.timings_ms["tts"] = out.ms
        turn.timings_ms["total"] = (time.perf_counter() - t0) * 1e3
        return turn

    def verify(self, audio: np.ndarray | None, sr: int, lang: str, memory_id: int, text: str | None = None) -> Turn:
        t0 = time.perf_counter()
        turn = Turn(uuid.uuid4().hex[:10], "verify", "listener", lang, lang)
        if text is None:
            res, timings, secs = self.transcribe(audio, sr, lang, [lang])
            turn.source_text, turn.asr_backend, turn.audio_seconds = res.text, res.backend, secs
            turn.timings_ms.update(timings)
        else:
            turn.source_text = text
        turn.english = self.english_of(turn.source_text, lang)
        result = self.memory.check_verification(memory_id, turn.english, turn.source_text, lang)
        msg_en = "Confirmed. Thank you." if result.get("ok") else "Not quite. Please listen again."
        turn.answer_en = msg_en
        turn.answer = self.translate(msg_en, "en", lang).text
        turn.verification = {"memory_id": memory_id, **result}
        turn.timings_ms["total"] = (time.perf_counter() - t0) * 1e3
        return turn

    def handover(self, lang: str) -> dict:
        en = self.memory.handover_en()
        from mindbridge.mt.text import split_sentences

        parts = split_sentences(en)
        text = (" " if lang != "zh" else "").join(self.mt.translate_batch(parts, "en", lang)) if lang != "en" else en
        return {"lang": lang, "text": text, "text_en": en, "structured": self.memory.handover_structured()}

    # ------------------------------------------------------------------ evidence
    def inventory(self) -> list[dict]:
        a, b = self.cfg.default_pair.split("-")
        rows = [
            {"stage": "Speech recognition", "model": self.asr.name, "unit": self.asr.compute_unit.upper(),
             "size_mb": round(files_size_mb(self.asr.model_files()), 1),
             "note": getattr(self.asr, "fallback_reason", "")},
            {"stage": "Translation", "model": self.mt.name, "unit": "CPU",
             "size_mb": round(files_size_mb(self.mt.model_files()), 1), "note": ""},
        ]
        if self.vad is not None:
            rows.insert(0, {"stage": "Voice activity", "model": "Silero VAD v5", "unit": "CPU",
                            "size_mb": round(files_size_mb([str(self.cfg.models_path / 'vad' / 'silero_vad.onnx')]), 1), "note": ""})
        if self.tts:
            for lang in (a, b):
                rows.append({"stage": f"Speech synthesis ({L.get(lang).name})", "model": L.get(lang).tts_voice,
                             "unit": "CPU", "size_mb": round(files_size_mb(self.tts.model_files([lang])), 1), "note": ""})
        rows.append({"stage": "Operational memory", "model": "Rule engine + SQLite", "unit": "CPU", "size_mb": 0.0, "note": ""})
        return rows
