from app.engine.understanding import build_follow_up, score_understanding

THRESHOLD = 70


def test_high_understanding():
    original = "Replace Filter B before restarting the machine."
    readback = "Understood, I need to replace Filter B before I restart the machine."
    score, understood, factors, missing = score_understanding(original, readback, THRESHOLD)
    assert understood
    assert score >= THRESHOLD
    assert len(factors) == 5


def test_low_understanding_missing_entity():
    original = "Replace Filter B before restarting the machine."
    readback = "Okay I will restart the machine."  # missing the filter step
    score, understood, factors, missing = score_understanding(original, readback, THRESHOLD)
    assert not understood
    assert any("filter" in m.lower() or "b" in m.lower() for m in missing) or missing


def test_confusion_lowers_score():
    original = "Lockout the pump before maintenance."
    readback = "What? Can you repeat that, I don't understand."
    score, understood, factors, missing = score_understanding(original, readback, THRESHOLD)
    assert not understood
    assert score < THRESHOLD


def test_follow_up_message():
    assert "verified" in build_follow_up(True, [], "ok").lower()
    assert build_follow_up(False, ["reference to 'filter b'"], "ok").endswith(".")
