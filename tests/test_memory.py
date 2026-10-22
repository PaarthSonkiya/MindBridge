from mindbridge.memory import MemoryEngine, MemoryStore
from mindbridge.memory.extractor import extract, find_entities


def engine():
    return MemoryEngine(MemoryStore(":memory:"))


def test_restriction_extracted_with_condition():
    ex = extract("Do not restart Machine 4 until the pressure valve is replaced.")
    assert ex.kind == "instruction" and ex.polarity == "forbid"
    assert ex.subject == "Machine 4" and ex.action_family == "start"
    assert ex.condition.startswith("until the pressure valve")
    assert ex.risk in ("high", "critical")


def test_kinds():
    assert extract("We will run Line 2 at half speed for the next two hours.").kind == "decision"
    assert extract("Machine 6 is vibrating again when it reaches 80 percent load.").kind == "issue"
    assert extract("I will replace the valve before the night shift.").kind == "commitment"
    assert extract("The valve was replaced and Machine 4 passed the pressure test.").kind == "outcome"
    assert extract("Can we restart machine 4?").kind == "question"
    assert extract("Machine 4 is running normally again.").kind == "outcome"
    assert extract("Machine 4 can only be restarted if maintenance has signed off.").kind == "exception"


def test_native_language_entities():
    assert find_entities("", "Không được khởi động lại máy số 4", "vi") == ["Machine 4"]
    assert find_entities("", "4번 기계를 다시 시작하지 마세요", "ko") == ["Machine 4"]
    assert find_entities("", "不要重新启动四号机器", "zh") == ["Machine 4"]
    assert find_entities("Check machine number four and line 2") == ["Machine 4", "Line 2"]


def test_conflict_then_resolution_then_recall():
    e = engine()
    r1 = e.ingest("Do not restart Machine 4 until the pressure valve is replaced.", "", "en", "Supervisor")
    assert r1.verification_question_en == "Quick check: can we restart Machine 4 now?"
    assert e.safety_light() == "red"

    r2 = e.ingest("Start machine number 4.", "", "en", "Supervisor")
    assert any(a["level"] == "red" for a in r2.alerts)
    assert r2.memory.status == "held"

    ans = e.answer("Can we restart machine four?")
    assert ans.startswith("Not yet")

    r3 = e.ingest("The valve was replaced and Machine 4 passed the pressure test.", "", "en", "Technician")
    assert any(m.text_en.startswith("Do not restart") for m in r3.resolved)
    assert e.answer("Can we restart machine 4?").startswith("Yes")


def test_small_talk_not_stored():
    e = engine()
    r = e.ingest("Good morning, how was your weekend", "", "en", "Operator")
    assert r.memory is None and not e.store.all()


def test_verification_answers():
    e = engine()
    m = e.ingest("Do not restart Machine 4 until the pressure valve is replaced.", "", "en", "Supervisor").memory
    assert e.check_verification(m.id, "No, not until the valve is replaced.", "Không, chưa được.", "vi")["ok"]
    m2 = e.ingest("Do not enter Zone 3 until the gas test is done.", "", "en", "Supervisor").memory
    assert not e.check_verification(m2.id, "Yes, we can.", "Có, được.", "vi")["ok"]


def test_commitment_cleared_by_outcome():
    e = engine()
    e.ingest("I will replace the valve before the night shift.", "", "en", "Technician")
    e.ingest("The valve has been replaced.", "", "en", "Technician")
    assert all(m.status != "active" for m in e.store.all() if m.kind == "commitment")


def test_handover_mentions_open_items():
    e = engine()
    e.ingest("Do not restart Machine 4 until the pressure valve is replaced.", "", "en", "Supervisor")
    e.ingest("Machine 6 is vibrating again.", "", "en", "Operator")
    h = e.handover_en()
    assert "restriction" in h and "Machine 6" in h
