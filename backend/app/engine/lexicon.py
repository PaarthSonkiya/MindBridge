"""Domain lexicons powering the offline heuristic engine.

These tables encode the industrial-communication knowledge the deterministic
engine needs so the system is useful with zero network access. When Claude is
enabled the same concepts are handled with far greater nuance, but the offline
path keeps the demo honest and reproducible.
"""

from __future__ import annotations

# --- Intent cues ----------------------------------------------------------
# Ordered by priority: the first matching category wins.
INTENT_CUES: list[tuple[str, tuple[str, ...]]] = [
    (
        "emergency",
        ("emergency", "evacuate", "fire", "explosion", "mayday", "call 911", "help now",
         "danger", "gas leak", "collapse"),
    ),
    (
        "warning",
        ("warning", "caution", "danger", "do not", "never", "risk", "hazard", "be careful",
         "watch out", "stop immediately", "high voltage"),
    ),
    (
        "escalation",
        ("escalate", "notify supervisor", "call the engineer", "get the manager",
         "raise a ticket", "report to"),
    ),
    (
        "approval",
        ("approved", "you may proceed", "permission granted", "cleared to", "go ahead",
         "authorized"),
    ),
    (
        "confirmation",
        ("confirmed", "understood", "copy that", "acknowledged", "i will", "i need to",
         "got it", "roger"),
    ),
    (
        "instruction",
        ("please", "make sure", "ensure", "replace", "inspect", "check", "tighten", "shut",
         "start", "stop", "restart", "lockout", "tag out", "install", "remove", "set",
         "verify", "before", "after"),
    ),
]

# --- Risk / hazard knowledge ---------------------------------------------
HAZARD_TERMS: dict[str, str] = {
    "lockout": "Lockout/Tagout (LOTO) energy-isolation procedure",
    "tagout": "Lockout/Tagout (LOTO) energy-isolation procedure",
    "loto": "Lockout/Tagout (LOTO) energy-isolation procedure",
    "high voltage": "Electrical / high-voltage exposure",
    "voltage": "Electrical exposure",
    "live wire": "Electrical / live conductor",
    "gas leak": "Hazardous gas release",
    "gas": "Hazardous gas exposure",
    "pressure": "Stored / high pressure",
    "pressurized": "Stored / high pressure",
    "confined space": "Confined-space entry hazard",
    "forklift": "Mobile-equipment / pedestrian hazard",
    "crane": "Overhead lifting / suspended load",
    "suspended load": "Overhead lifting / suspended load",
    "chemical": "Hazardous chemical exposure",
    "acid": "Corrosive chemical exposure",
    "explosion": "Explosive atmosphere",
    "fire": "Fire hazard",
    "hot work": "Hot work / ignition source",
    "fall": "Working at height / fall hazard",
    "scaffold": "Working at height / scaffold",
    "shutdown": "Equipment shutdown procedure",
    "emergency stop": "Emergency stop / e-stop",
    "evacuate": "Emergency evacuation",
}

CRITICAL_TERMS = {"explosion", "evacuate", "gas leak", "fire", "emergency stop", "mayday"}
HIGH_TERMS = {"lockout", "tagout", "loto", "high voltage", "confined space", "suspended load",
              "shutdown", "live wire"}

# --- Technical glossary for expertise adaptation -------------------------
# Maps engineer-level jargon to plain-language explanations for operators.
GLOSSARY: dict[str, str] = {
    "cavitation": "the pump pulling in air bubbles because the incoming pressure is too low",
    "npsh": "the incoming pressure available at the pump inlet",
    "torque": "how tightly the bolt is fastened",
    "calibrate": "adjust so the readings are accurate",
    "tolerance": "the allowed amount of variation",
    "interlock": "the safety switch that blocks operation when conditions are unsafe",
    "actuator": "the part that physically moves the valve or arm",
    "ph": "how acidic or basic the liquid is",
    "viscosity": "how thick or runny the fluid is",
    "loto": "locking and tagging the machine so it cannot be switched on",
    "amperage": "the amount of electrical current",
    "rpm": "how fast it is spinning",
}

# --- Minimal EN<->VI phrase book for the offline translator --------------
# A small, hand-verified industrial phrase book. The Claude path handles the
# full language; this keeps the offline demo intelligible for common terms.
EN_VI: dict[str, str] = {
    "stop": "dừng lại",
    "stop the machine": "dừng máy",
    "start the machine": "khởi động máy",
    "restart the machine": "khởi động lại máy",
    "replace the filter": "thay bộ lọc",
    "check the pressure": "kiểm tra áp suất",
    "wear your helmet": "đội mũ bảo hộ",
    "danger": "nguy hiểm",
    "warning": "cảnh báo",
    "emergency": "khẩn cấp",
    "evacuate now": "sơ tán ngay",
    "do not enter": "không được vào",
    "lockout the power": "khóa nguồn điện",
    "confirmed": "đã xác nhận",
    "understood": "đã hiểu",
    "be careful": "cẩn thận",
    "high voltage": "điện áp cao",
}

VI_EN = {v: k for k, v in EN_VI.items()}
