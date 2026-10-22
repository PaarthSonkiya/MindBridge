"""The NPU decoder loop, tested against fake ONNX Runtime sessions that enforce
Qualcomm AI Hub's Whisper I/O contract (shapes, dtypes, quantisation, mask, positions).

Two variants: float I/O, and the quantised I/O of AI Hub's real QCS6490 build
(uint16 features / mask / logits, uint8 KV caches; parameters from metadata.json)."""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import numpy as np
import pytest

from mindbridge import languages as L

H, D, SLOTS, LAYERS, VOCAB = 2, 8, 200, 2, 51865
# Real values from AI Hub's whisper_small_quantized QCS6490 metadata.json
Q_FEAT = (4.677007018472068e-05, 32072)
Q_MASK = (0.0015259021893143654, 65535)
Q_LOGITS = (0.0012925398768857121, 17867)
Q_CACHE = (0.05, 128)


class Spec(SimpleNamespace):
    pass


def _t(quant: bool, kind: str) -> str:
    if not quant:
        return "tensor(float)"
    return {"feat": "tensor(uint16)", "mask": "tensor(uint16)", "logits": "tensor(uint16)", "cache": "tensor(uint8)"}[kind]


class FakeEncoder:
    def __init__(self, quant):
        self.quant = quant

    def get_inputs(self):
        return [Spec(name="input_features", shape=[1, 80, 3000], type=_t(self.quant, "feat"))]

    def get_outputs(self):
        return [Spec(name=f"{kv}_cache_cross_{i}", type=_t(self.quant, "cache")) for i in range(LAYERS) for kv in "kv"]

    def run(self, names, feeds):
        x = feeds["input_features"]
        assert x.shape == (1, 80, 3000)
        if self.quant:
            assert x.dtype == np.uint16
            # silence is log-mel -1.5, which is exactly the bottom of AI Hub's calibrated range (q = 0)
            deq = (x.astype(np.float32) - Q_FEAT[1]) * Q_FEAT[0]
            assert np.allclose(deq, -1.5, atol=1e-3)
        else:
            assert x.dtype == np.float32
        dt = np.uint8 if self.quant else np.float32
        return [np.full((H, 1, D, 1500) if n.startswith("k") else (H, 1, 1500, D), 7, dt) for n in names]


class FakeDecoder:
    """Emits language 'ko' at the language-ID step, then the scripted tokens, then EOT."""

    def __init__(self, script, quant):
        self.script, self.quant = script, quant
        self.fed: list[int] = []

    def get_inputs(self):
        ins = [Spec(name="input_ids", shape=[1, 1], type="tensor(int32)"),
               Spec(name="attention_mask", shape=[1, 1, 1, SLOTS], type=_t(self.quant, "mask"))]
        for i in range(LAYERS):
            ins += [Spec(name=f"k_cache_self_{i}_in", shape=[H, 1, D, SLOTS - 1], type=_t(self.quant, "cache")),
                    Spec(name=f"v_cache_self_{i}_in", shape=[H, 1, SLOTS - 1, D], type=_t(self.quant, "cache"))]
        for i in range(LAYERS):
            ins += [Spec(name=f"k_cache_cross_{i}", shape=[H, 1, D, 1500], type=_t(self.quant, "cache")),
                    Spec(name=f"v_cache_cross_{i}", shape=[H, 1, 1500, D], type=_t(self.quant, "cache"))]
        ins.append(Spec(name="position_ids", shape=[1], type="tensor(int32)"))
        return ins

    def get_outputs(self):
        outs = [Spec(name="logits", type=_t(self.quant, "logits"))]
        for i in range(LAYERS):
            outs += [Spec(name=f"k_cache_self_{i}_out", type=_t(self.quant, "cache")),
                     Spec(name=f"v_cache_self_{i}_out", type=_t(self.quant, "cache"))]
        return outs

    def run(self, names, feeds):
        pos = int(feeds["position_ids"][0])
        assert feeds["input_ids"].dtype == np.int32 and pos == len(self.fed)
        mask = feeds["attention_mask"][0, 0, 0]
        if self.quant:
            assert mask.dtype == np.uint16
            open_val, closed_val = 65535, 0  # 0.0 and -100.0 under the real parameters
        else:
            open_val, closed_val = 0.0, -100.0
        assert int((mask == open_val).sum()) == pos + 1 and mask[SLOTS - 1 - pos] == open_val
        assert int((mask == closed_val).sum()) == SLOTS - pos - 1
        if pos == 0 and self.quant:
            assert all((feeds[n] == Q_CACHE[1]).all() for n in feeds if "cache_self" in n)  # quantised zeros
        assert all((feeds[n] == 7).all() for n in feeds if "cache_cross" in n)  # passed through raw
        self.fed.append(int(feeds["input_ids"][0, 0]))
        logits = np.full(VOCAB, -3.0, np.float32)
        if pos == 0:
            logits[L.LANGUAGES["ko"].whisper_token_id] = 5.0
        else:
            k = pos - 3  # logits after feeding <notimestamps> (pos 3) predict the first text token
            logits[self.script[k] if 0 <= k < len(self.script) else L.WHISPER_EOT] = 10.0
        if self.quant:
            s, z = Q_LOGITS
            logits = np.clip(np.rint(logits / s) + z, 0, 65535).astype(np.uint16)
        outs = [logits.reshape(1, VOCAB, 1, 1)]
        for n in names[1:]:
            outs.append(feeds[n.replace("_out", "_in")])
        return outs


def _metadata(quant: bool) -> dict:
    if not quant:
        return {}
    qp = lambda p: {"quantization_parameters": {"scale": p[0], "zero_point": p[1]}}  # noqa: E731
    dec_in = {"attention_mask": qp(Q_MASK)}
    dec_out = {"logits": qp(Q_LOGITS)}
    for i in range(LAYERS):
        for kv in "kv":
            dec_in[f"{kv}_cache_self_{i}_in"] = qp(Q_CACHE)
            dec_out[f"{kv}_cache_self_{i}_out"] = qp(Q_CACHE)
    return {"model_files": {"encoder.onnx": {"inputs": {"input_features": qp(Q_FEAT)}},
                            "decoder.onnx": {"inputs": dec_in, "outputs": dec_out}}}


@pytest.fixture(params=[False, True], ids=["float-io", "quantised-io"])
def qnn(request, monkeypatch, tmp_path):
    from mindbridge.asr import whisper_qnn

    quant = request.param
    (tmp_path / "encoder.onnx").write_bytes(b"x")
    (tmp_path / "decoder.onnx").write_bytes(b"x")
    if quant:
        (tmp_path / "metadata.json").write_text(json.dumps(_metadata(True)))
    (tmp_path / "whisper-tokens.txt").write_text(
        f"{base64.b64encode(b'hi').decode()} 100\n{base64.b64encode(b' there').decode()} 101\n"
    )
    dec = FakeDecoder([100, 101], quant)
    sessions = {"encoder.onnx": FakeEncoder(quant), "decoder.onnx": dec}
    monkeypatch.setattr(whisper_qnn, "make_session", lambda p, b, t: sessions[p.name])
    return whisper_qnn.WhisperQnn(tmp_path, backend="qnn"), dec


def test_forced_language_prompt_and_greedy_decode(qnn):
    eng, dec = qnn
    res = eng.transcribe(np.zeros(16000, np.float32), "vi")
    assert res.text == "hi there" and res.language == "vi" and res.num_tokens == 2
    assert dec.fed[:4] == [L.WHISPER_SOT, L.LANGUAGES["vi"].whisper_token_id, L.WHISPER_TRANSCRIBE, L.WHISPER_NO_TIMESTAMPS]


def test_language_detection_among_candidates(qnn):
    eng, dec = qnn
    res = eng.transcribe(np.zeros(16000, np.float32), None, ["vi", "ko"])
    assert res.language == "ko" and dec.fed[1] == L.LANGUAGES["ko"].whisper_token_id


def test_missing_quant_params_is_a_clear_error(monkeypatch, tmp_path):
    from mindbridge.asr import whisper_qnn

    for f in ("encoder.onnx", "decoder.onnx", "whisper-tokens.txt"):
        (tmp_path / f).write_text("")
    sessions = {"encoder.onnx": FakeEncoder(True), "decoder.onnx": FakeDecoder([], True)}
    monkeypatch.setattr(whisper_qnn, "make_session", lambda p, b, t: sessions[p.name])
    with pytest.raises(RuntimeError, match="quantisation parameters"):
        whisper_qnn.WhisperQnn(tmp_path)


def test_loop_guard():
    from mindbridge.asr.whisper_qnn import _looping

    assert _looping([5, 7, 7, 7])
    assert _looping([1, 2, 3, 1, 2, 3, 1, 2, 3])
    assert not _looping([1, 2, 3, 4, 5])


def test_specials_for_large_v3_vocab():
    sp_small, sp_turbo = L.whisper_specials(51865), L.whisper_specials(51866)
    assert (sp_small["transcribe"], sp_small["no_timestamps"]) == (50359, 50363)
    assert (sp_turbo["transcribe"], sp_turbo["no_timestamps"]) == (50360, 50364)
    assert sp_turbo["sot"] == sp_small["sot"] == 50258
