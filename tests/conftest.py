"""Shared fakes so tests run anywhere (no models, no NPU, no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mindbridge.asr.base import AsrEngine, AsrResult  # noqa: E402
from mindbridge.mt.nllb_ct2 import MtResult  # noqa: E402

EN_VI = {
    "Do not restart Machine 4 until the pressure valve is replaced.": "Không được khởi động lại máy số 4 cho đến khi thay van áp suất.",
    "Start machine 4.": "Khởi động máy số 4.",
}
VI_EN = {v: k for k, v in EN_VI.items()} | {
    "Máy số 6 lại rung.": "Machine 6 is vibrating again.",
    "Không, chưa được.": "No, not yet.",
    "Có thể khởi động lại máy số 4 không?": "Can we restart machine 4?",
}


class FakeAsr(AsrEngine):
    name = "fake-asr"
    compute_unit = "cpu"

    def __init__(self):
        self.next_text = ""

    def transcribe(self, audio, language, candidates=None):
        return AsrResult(self.next_text, language or (candidates or ["en"])[0], self.name, {"encoder": 1.0})


class FakeMt:
    name = "fake-mt"
    compute_unit = "cpu"

    def translate(self, text, src, tgt):
        table = EN_VI if (src, tgt) == ("en", "vi") else VI_EN if (src, tgt) == ("vi", "en") else {}
        return MtResult(table.get(text, text if tgt == "en" else f"<{tgt}>{text}"), src, tgt, {"mt": 2.0})

    def translate_batch(self, sents, src, tgt):
        return [self.translate(s, src, tgt).text for s in sents]

    def translate_many(self, texts, src, tgt):
        return [self.translate(t, src, tgt).text for t in texts]

    def model_files(self):
        return []


class FakeTts:
    def available(self, lang):
        return True

    def synthesize(self, text, lang):
        from mindbridge.tts import TtsResult

        return TtsResult(np.zeros(1600, dtype=np.float32), 16000, 3.0)

    def preload(self, langs):
        pass

    def model_files(self, langs):
        return []


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    from mindbridge import pipeline
    from mindbridge.config import AppConfig
    from mindbridge.memory import MemoryEngine, MemoryStore

    cfg = AppConfig()
    cfg.models_dir = str(tmp_path / "models")
    cfg.data_dir = str(tmp_path / "data")
    b = pipeline.MindBridge.__new__(pipeline.MindBridge)
    b.cfg = cfg
    b.load_ms = {}
    b.vad = None
    b.asr = FakeAsr()
    b.mt = FakeMt()
    b.tts = FakeTts()
    b.memory = MemoryEngine(MemoryStore(tmp_path / "mem.db"))
    import threading

    b._lock = threading.Lock()
    return b
