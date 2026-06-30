from app.engine.risk import assess_risk
from app.models.schemas import RiskLevel


def test_no_risk():
    r = assess_risk("Please log the daily production numbers.")
    assert r.level == RiskLevel.NONE
    assert not r.requires_confirmation


def test_critical_risk():
    r = assess_risk("Gas leak detected, evacuate immediately!")
    assert r.level == RiskLevel.CRITICAL
    assert r.requires_confirmation
    assert r.hazards


def test_high_risk_loto():
    r = assess_risk("Perform lockout before servicing the conveyor.")
    assert r.level == RiskLevel.HIGH
    assert r.requires_confirmation


def test_medium_risk_multiple_signals():
    r = assess_risk("Watch the forklift near the chemical store.")
    assert r.level in {RiskLevel.MEDIUM, RiskLevel.HIGH}
