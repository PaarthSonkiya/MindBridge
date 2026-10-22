import time

import numpy as np
from fastapi.testclient import TestClient


def test_talk_turn_translates_and_remembers(bridge):
    turn = bridge.talk(None, 16000, "en", "vi", "Supervisor",
                       text="Do not restart Machine 4 until the pressure valve is replaced.")
    assert turn.translation.startswith("Không được khởi động lại máy số 4")
    assert turn.memory and turn.memory["subject"] == "Machine 4"
    assert turn.verification and turn.verification["lang"] == "vi"
    assert turn.tts_audio is not None and "mt" in turn.timings_ms


def test_audio_turn_uses_asr(bridge):
    bridge.asr.next_text = "Máy số 6 lại rung."
    turn = bridge.talk(np.zeros(16000, np.float32), 16000, "vi", "en", "Operator")
    assert turn.source_text == "Máy số 6 lại rung." and turn.translation == "Machine 6 is vibrating again."
    assert turn.memory["kind"] == "issue" and turn.memory["subject"] == "Machine 6"
    assert turn.timings_ms["asr"] >= 0


def test_ask_answers_from_memory_in_askers_language(bridge):
    bridge.talk(None, 16000, "en", "vi", "Supervisor", text="Do not restart Machine 4 until the pressure valve is replaced.")
    turn = bridge.ask(None, 16000, "vi", text="Có thể khởi động lại máy số 4 không?")
    assert turn.answer_en.startswith("Not yet")


def test_server_text_flow_and_events(bridge):
    from mindbridge.server import create_app

    app = create_app(bridge.cfg, bridge)
    with TestClient(app) as client:
        st = client.get("/api/status").json()
        assert st["sides"]["a"]["lang"] == "en" and st["sides"]["b"]["lang"] == "vi"
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "hello"
            client.post("/api/text", json={"side": "a", "text": "Do not restart Machine 4 until the pressure valve is replaced."})
            seen = set()
            deadline = time.time() + 5
            while time.time() < deadline and not {"turn", "turn_update", "memory"} <= seen:
                seen.add(ws.receive_json()["type"])
            assert {"turn", "turn_update", "memory"} <= seen
        mem = client.get("/api/memory").json()
        assert mem["light"] == "red" and mem["items"][0]["subject"] == "Machine 4"
        h = client.get("/api/handover?lang=en").json()
        assert "restriction" in h["text_en"]
        assert client.post("/api/pair", json={"pair": "vi-ko"}).json()["sides"]["a"]["lang"] == "ko"
