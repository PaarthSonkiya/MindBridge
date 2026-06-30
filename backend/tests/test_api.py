import os

os.environ["MINDBRIDGE_FORCE_OFFLINE"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["engine"] == "offline-heuristic"


def test_process_pipeline():
    resp = client.post(
        "/api/process",
        json={
            "text": "Replace Filter B before restarting the machine.",
            "source_lang": "en",
            "target_lang": "vi",
            "listener_expertise": "operator",
            "session_id": "test-1",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "instruction"
    assert body["requires_readback"] is True
    assert body["key_points"]


def test_verify_and_handover_flow():
    client.post(
        "/api/process",
        json={
            "text": "Lockout the conveyor before clearing the jam.",
            "session_id": "test-2",
            "listener_expertise": "technician",
        },
    )
    verify = client.post(
        "/api/verify",
        json={
            "session_id": "test-2",
            "original_text": "Lockout the conveyor before clearing the jam.",
            "readback_text": "Understood, I will lockout the conveyor before clearing the jam.",
        },
    )
    assert verify.status_code == 200
    assert verify.json()["understood"] is True

    handover = client.post("/api/handover", json={"session_id": "test-2"})
    assert handover.status_code == 200
    assert handover.json()["safety_observations"]
