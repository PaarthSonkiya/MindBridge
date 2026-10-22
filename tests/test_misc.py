import socket

import numpy as np
import pytest


def test_offline_guard_blocks_external_allows_loopback():
    from mindbridge import offline_guard

    offline_guard.install()
    with pytest.raises(offline_guard.NetworkBlocked):
        socket.create_connection(("93.184.216.34", 80), timeout=1)
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    c = socket.create_connection(srv.getsockname(), timeout=1)
    c.close()
    srv.close()


def test_mel_matches_reference_when_available():
    from mindbridge.asr.mel import log_mel

    x = (np.random.RandomState(0).randn(16000 * 2) * 0.1).astype(np.float32)
    mine = log_mel(x)
    assert mine.shape == (1, 80, 3000) and mine.dtype == np.float32
    tf = pytest.importorskip("transformers")
    ref = tf.WhisperFeatureExtractor(feature_size=80)(x, sampling_rate=16000, return_tensors="np")["input_features"]
    assert np.abs(ref - mine).max() < 1e-4


def test_sentence_split_and_simplified_chinese():
    from mindbridge.mt.text import clean_asr, split_sentences

    assert split_sentences("Stop. Wait here! Ok?") == ["Stop.", "Wait here!", "Ok?"]
    assert split_sentences("停机。等一下！") == ["停机。", "等一下！"]
    out = clean_asr("在更換壓力閥之前", "zh")
    assert "换" in out or "更換" not in out  # converted when opencc is installed


def test_config_env_override(monkeypatch):
    from mindbridge.config import load_config

    monkeypatch.setenv("MINDBRIDGE_ASR_BACKEND", "cpu")
    monkeypatch.setenv("MINDBRIDGE_PORT", "9000")
    cfg = load_config()
    assert cfg.asr.backend == "cpu" and cfg.port == 9000


def test_bench_loader(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("rb", Path(__file__).parent.parent / "bench" / "run_benchmark.py")
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)
    (tmp_path / "a.csv").write_text("English,Vietnamese\nStop the machine.,Dừng máy lại.\n", encoding="utf-8")
    (tmp_path / "vi-ko.tsv").write_text("src\ttgt\nDừng máy.\t기계를 멈추세요.\n", encoding="utf-8")
    pairs = rb.load_pairs(tmp_path)
    assert pairs[("vi", "en")][0] == {"a": "Dừng máy lại.", "b": "Stop the machine.", "file": "a.csv"}
    assert pairs[("vi", "ko")][0]["b"] == "기계를 멈추세요."
    assert rb.error_rate("dừng máy lại", "dừng máy", "vi") == pytest.approx(1 / 3)


def test_bench_loader_audio_columns_and_sheets(tmp_path):
    import importlib.util
    from pathlib import Path

    import openpyxl

    spec = importlib.util.spec_from_file_location("rb2", Path(__file__).parent.parent / "bench" / "run_benchmark.py")
    rb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rb)
    (tmp_path / "t.csv").write_text("id,audio_vi,vi,ko\n1,a/1.wav,Dừng máy.,기계를 멈추세요.\n", encoding="utf-8")
    wb = openpyxl.Workbook()
    wb.active.append(["Vietnamese", "English"])
    wb.active.append(["Dừng máy.", "Stop the machine."])
    ws2 = wb.create_sheet("ko")
    ws2.append(["Vietnamese", "Korean"])
    ws2.append(["Dừng máy.", "기계를 멈추세요."])
    wb.save(tmp_path / "s.xlsx")
    pairs = rb.load_pairs(tmp_path)
    ko = pairs[("vi", "ko")]
    assert any(i["a"] == "Dừng máy." and i.get("audio_a", "").endswith("1.wav") for i in ko)
    assert len(ko) == 2 and pairs[("vi", "en")][0]["b"] == "Stop the machine."
