from app.engine.intent import classify_intent
from app.models.schemas import Intent


def test_instruction():
    assert classify_intent("Please replace Filter B before restarting the machine.") == Intent.INSTRUCTION


def test_question():
    assert classify_intent("Why did the machine stop?") == Intent.QUESTION


def test_emergency_overrides_question():
    assert classify_intent("Is there a gas leak in zone 3?!") == Intent.EMERGENCY


def test_warning():
    assert classify_intent("Warning: high voltage, do not touch the panel.") == Intent.WARNING


def test_confirmation():
    assert classify_intent("Understood, I will replace the filter.") == Intent.CONFIRMATION


def test_emergency():
    assert classify_intent("Emergency! Evacuate the building now.") == Intent.EMERGENCY
