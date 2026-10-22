"""The NPU decoder loop, tested against a fake ONNX Runtime session that enforces
Qualcomm AI Hub's Whisper I/O contract (shapes, mask filling, position ids)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from mindbridge import languages as L

H, D, SLOTS, LAYERS, VOCAB = 2, 8, 200, 2, 51865


class Spec(SimpleNamespace):
    pass


class FakeEncoder:
    def get_inputs(self):
        return [Spec(name="input_features", shape=[1, 80, 3000], type="tensor(float)")]

    def get_outputs(self):
        return [Spec(name=f"{kv}_cache_cross_{i}") for i in range(LAYERS) for kv in "kv"]

    def run(self, names, feeds):
        x = feeds["input_features"]
        assert x.shape == (1, 80, 3000) and x.dtype == np.float32
        return [np.zeros((H, 1, D, 1500) if n.startswith("k") else (H, 1, 1500, D), np.float32) for n in names]


class FakeDecoder:
    """Emits language token 'ko' when asked, then the scripted text tokens, then EOT."""

    def __init__(self, script):
        self.script = script
        self.fed: list[int] = []

    def get_inputs(self):
        ins = [Spec(name="input_ids", shape=[1, 1], type="tensor(int32)"),
               Spec(name="attention_mask", shape=[1, 1, 1, SLOTS], type="tensor(float)")]
        for i in range(LAYERS):
            ins += [Spec(name=f"k_cache_self_{i}_in", shape=[H, 1, D, SLOTS - 1], type="tensor(float)"),
                    Spec(name=f"v_cache_self_{i}_in", shape=[H, 1, SLOTS - 1, D], type="tensor(float)")]
        for i in range(LAYERS):
            ins += [Spec(name=f"k_cache_cross_{i}", shape=[H, 1, D, 1500], type="tensor(float)"),
                    Spec(name=f"v_cache_cross_{i}", shape=[H, 1, 1500, D], type="tensor(float)")]
        ins.append(Spec(name="position_ids", shape=[1], type="tensor(int32)"))
        return ins

    def get_outputs(self):
        outs = [Spec(name="logits")]
        for i in range(LAYERS):
            outs += [Spec(name=f"k_cache_self_{i}_out"), Spec(name=f"v_cache_self_{i}_out")]
        return outs

    def run(self, names, feeds):
        pos = int(feeds["position_ids"][0])
        assert feeds["input_ids"].dtype == np.int32
        assert pos == len(self.fed)
        mask = feeds["attention_mask"][0, 0, 0]
        assert int((mask == 0).sum()) == pos + 1 and mask[SLOTS - 1 - pos] == 0
        self.fed.append(int(feeds["input_ids"][0, 0]))
        logits = np.zeros((1, VOCAB, 1, 1), np.float32)
        if pos == 0:
            logits[0, L.LANGUAGES["ko"].whisper_token_id] = 5.0  # language-ID step
        else:
            k = pos - 3  # logits after feeding <notimestamps> (pos 3) predict the first text token
            nxt = self.script[k] if 0 <= k < len(self.script) else L.WHISPER_EOT
            logits[0, nxt] = 10.0
        outs = [logits]
        for n in names[1:]:
            outs.append(feeds[n.replace("_out", "_in")] + 1)
        return outs


@pytest.fixture
def qnn(monkeypatch, tmp_path):
    from mindbridge.asr import whisper_qnn

    (tmp_path / "encoder.onnx").write_bytes(b"x")
    (tmp_path / "decoder.onnx").write_bytes(b"x")
    # token table: id 100 -> "hi", 101 -> " there"
    import base64

    (tmp_path / "whisper-tokens.txt").write_text(
        f"{base64.b64encode(b'hi').decode()} 100\n{base64.b64encode(b' there').decode()} 101\n"
    )
    dec = FakeDecoder([100, 101])
    sessions = {"encoder.onnx": FakeEncoder(), "decoder.onnx": dec}
    monkeypatch.setattr(whisper_qnn, "make_session", lambda p, b, t: sessions[p.name])
    eng = whisper_qnn.WhisperQnn(tmp_path, backend="qnn")
    return eng, dec


def test_forced_language_prompt_and_greedy_decode(qnn):
    eng, dec = qnn
    res = eng.transcribe(np.zeros(16000, np.float32), "vi")
    assert res.text == "hi there" and res.language == "vi" and res.num_tokens == 2
    assert dec.fed[:4] == [L.WHISPER_SOT, L.LANGUAGES["vi"].whisper_token_id, L.WHISPER_TRANSCRIBE, L.WHISPER_NO_TIMESTAMPS]


def test_language_detection_among_candidates(qnn):
    eng, dec = qnn
    res = eng.transcribe(np.zeros(16000, np.float32), None, ["vi", "ko"])
    assert res.language == "ko"
    assert dec.fed[1] == L.LANGUAGES["ko"].whisper_token_id


def test_loop_guard():
    from mindbridge.asr.whisper_qnn import _looping

    assert _looping([5, 7, 7, 7])
    assert _looping([1, 2, 3, 1, 2, 3, 1, 2, 3])
    assert not _looping([1, 2, 3, 4, 5])
