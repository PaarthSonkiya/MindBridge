"""Deterministic, explainable extraction of Operational Memory Objects.

Runs on the English pivot of every utterance (MindBridge's internal memory
language) plus a few native-language equipment patterns, so it works for
VI / KO / ZH speakers too. No language model is needed on the QCS6490 — the
rules are fast (<1 ms), auditable, and never hallucinate an instruction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Equipment entities
# ---------------------------------------------------------------------------
EQUIPMENT = (
    "machine|line|pump|valve|conveyor|press|station|tank|boiler|compressor|robot|motor|"
    "furnace|oven|belt|mold|mould|generator|crane|forklift|chiller|dryer|mixer|cutter|"
    "lathe|welder|panel|cabinet|gate|zone|area|bay|dock|room|hopper|extruder|reactor|"
    "filter|fan|heater|cooler|cell|unit|kiln|shredder|sorter|scanner|printer|truck|rack"
)
_NUMWORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "first": "1",
    "second": "2", "third": "3", "fourth": "4", "fifth": "5",
}
_NUM = r"(\d{1,4}[a-z]?|[a-z]\b|" + "|".join(_NUMWORDS) + r")"
_EQUIP_AFTER = re.compile(rf"\b({EQUIPMENT})s?+\s*(?:no\.?|number|num\.?|#)?\s*{_NUM}", re.I)
_EQUIP_BEFORE = re.compile(rf"\b(?:number|no\.?|#)\s*{_NUM}\s+({EQUIPMENT})\b", re.I)
_CODE = re.compile(r"\b([A-Z]{1,4})-?(\d{1,4})\b")
_EQUIP_BARE = re.compile(rf"\b(?:the|this|that)\s+((?:[a-z]+\s)?(?:{EQUIPMENT}))\b", re.I)

_VI_EQUIP = {"máy": "Machine", "dây chuyền": "Line", "chuyền": "Line", "bơm": "Pump", "van": "Valve",
             "băng tải": "Conveyor", "lò": "Furnace", "máy nén": "Compressor", "bồn": "Tank", "khu": "Zone"}
_VI_RE = re.compile(r"(máy nén|dây chuyền|băng tải|chuyền|máy|bơm|van|lò|bồn|khu)\s*(?:số\s*)?(\d{1,4}[a-z]?)", re.I)
_KO_EQUIP = {"기계": "Machine", "라인": "Line", "펌프": "Pump", "밸브": "Valve", "컨베이어": "Conveyor", "호기": "Machine"}
_KO_RE = re.compile(r"(\d{1,4})\s*(?:번\s*)?(기계|라인|펌프|밸브|컨베이어|호기)")
_ZH_EQUIP = {"机器": "Machine", "机": "Machine", "线": "Line", "生产线": "Line", "泵": "Pump", "阀": "Valve", "传送带": "Conveyor"}
_ZH_DIG = {"一": "1", "二": "2", "两": "2", "三": "3", "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}
_ZH_RE = re.compile(r"(?:第\s*)?(\d{1,4}|[一二两三四五六七八九十])\s*(?:号|台|条)?\s*(生产线|机器|传送带|机|线|泵|阀)")


def _canon(kind: str, num: str) -> str:
    num = _NUMWORDS.get(num.lower(), num)
    num = num.upper() if len(num) == 1 and num.isalpha() else num
    return f"{kind.capitalize()} {num}"


def find_entities(text_en: str, source_text: str = "", source_lang: str = "en") -> list[str]:
    ents: list[str] = []

    def add(e: str):
        if e not in ents:
            ents.append(e)

    if source_lang == "vi":
        for m in _VI_RE.finditer(source_text):
            add(_canon(_VI_EQUIP[m.group(1).lower()], m.group(2)))
    elif source_lang == "ko":
        for m in _KO_RE.finditer(source_text):
            add(_canon(_KO_EQUIP[m.group(2)], m.group(1)))
    elif source_lang == "zh":
        for m in _ZH_RE.finditer(source_text):
            add(_canon(_ZH_EQUIP[m.group(2)], _ZH_DIG.get(m.group(1), m.group(1))))
    for m in _EQUIP_AFTER.finditer(text_en):
        if m.group(2).lower() in ("a", "i") and not m.group(0)[-1].isupper():
            continue  # "line a" false positives like "a line a"
        add(_canon(m.group(1), m.group(2)))
    for m in _EQUIP_BEFORE.finditer(text_en):
        add(_canon(m.group(2), m.group(1)))
    for m in _CODE.finditer(text_en):
        if m.group(1) not in {"I", "A", "OK", "AM", "PM"}:
            add(f"{m.group(1)}-{m.group(2)}")
    if not ents:
        m = _EQUIP_BARE.search(text_en)
        if m:
            phrase = m.group(1).lower()
            if phrase.split()[0] in ("whole", "same", "other", "next", "new", "old", "main"):
                phrase = " ".join(phrase.split()[1:]) or phrase
            add(phrase[0].upper() + phrase[1:])
    return ents


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
ACTION_FAMILIES: dict[str, tuple[str, ...]] = {
    "start": ("restart", "re-start", "start up", "start", "turn on", "switch on", "power on", "power up",
              "run", "resume", "operate", "reboot", "boot", "activate", "reopen", "use"),
    "stop": ("shut down", "shut off", "turn off", "switch off", "power off", "stop", "halt", "pause",
             "cut the power", "cut power", "isolate", "lock out"),
    "enter": ("go into", "go inside", "go in", "enter", "walk into", "open the door", "open"),
    "touch": ("touch", "handle", "hold"),
    "load": ("load", "feed", "fill", "refill", "lift", "move", "carry"),
    "ppe": ("wear", "put on"),
    "repair": ("replace", "change", "repair", "fix", "clean", "inspect", "check", "tighten", "maintain",
               "service", "lubricate", "calibrate", "adjust", "test"),
}
_VERB_TO_FAMILY: list[tuple[str, str]] = sorted(
    ((v, fam) for fam, verbs in ACTION_FAMILIES.items() for v in verbs), key=lambda x: -len(x[0])
)


def _verb_pattern(verb: str) -> str:
    parts = verb.split(" ")
    head = re.escape(parts[0])
    stem = head[:-1] if head.endswith("e") else head
    head_rx = rf"(?:{head}|{stem}(?:e|es|ed|ing|s)|{head}(?:s|ed|ing|n))"
    if verb in ("run",):
        head_rx = r"(?:run|runs|running|ran)"
    if verb in ("shut down", "shut off"):
        head_rx = r"(?:shut|shuts|shutting)"
    rest = "".join(rf"\s+{re.escape(p)}" for p in parts[1:])
    return rf"\b{head_rx}{rest}\b"


_VERB_RX = [(re.compile(_verb_pattern(v), re.I), v, fam) for v, fam in _VERB_TO_FAMILY]


def find_action(text: str) -> tuple[str, str, int]:
    """Return (verb, family, position) of the earliest action verb in ``text``."""
    best: tuple[str, str, int] = ("", "", 10**9)
    for rx, verb, fam in _VERB_RX:
        m = rx.search(text)
        if m and m.start() < best[2]:
            best = (verb, fam, m.start())
    return best if best[0] else ("", "", -1)


# ---------------------------------------------------------------------------
# Cues
# ---------------------------------------------------------------------------
_NEG = re.compile(
    r"\b(do not|don't|dont|does not|doesn't|never|must not|mustn't|cannot|can't|can not|should not|"
    r"shouldn't|not allowed|is not allowed|are not allowed|prohibited|forbidden|no one (?:should|may|can)|"
    r"nobody (?:should|may|can)|avoid|stay away|keep away|not to)\b",
    re.I,
)
_REQ = re.compile(r"^(please\s+)?(make sure|ensure|remember to|you (?:must|need to|have to|should)|must|need to|have to)\b", re.I)
_COND = re.compile(r"\b(until|unless|before|only after|only if|after|when|as soon as|once|till|if)\b\s+(.+?)(?:[.!?]|$)", re.I)
_QUESTION_START = re.compile(
    r"^(?:(?:what|when|where|who|why|how|which)\b|(?:can|could|may|is|are|was|were|does|did|should|will|would|has|have|"
    r"do)\s+(?:i|we|you|they|it|he|she|the|this|that|machine|line|anyone|someone)\b)",
    re.I,
)
_OUTCOME = re.compile(
    r"\b(has been|have been|was|were|is now|are now|got|been|just|already|finished|completed|done)\b.*?\b("
    r"replaced|fixed|repaired|completed|finished|done|cleaned|installed|passed|resolved|restored|changed|"
    r"tested|signed off|approved|inspected|checked|tightened|calibrated|working|normal)\b"
    r"|\b(passed the (?:pressure |safety )?test|(?:is|are|was) (?:working|running|operating) (?:again|now|normally|fine)|"
    r"(?:works|runs) (?:again|normally)|back to normal|"
    r"(?:have|has|had) (?:replaced|fixed|repaired|changed|cleaned|finished|completed)|"
    r"(?:i|we) (?:replaced|fixed|repaired|changed|cleaned|finished|completed|installed))\b",
    re.I,
)
_ISSUE = re.compile(
    r"\b(vibrat\w*|leak\w*|overheat\w*|broken|breaks?|jamm?\w*|stuck|nois[ey]\w*|smok\w*|alarm\w*|error\w*|fault\w*|"
    r"crack\w*|not working|doesn't work|does not work|isn't working|is not working|fail\w*|problem\w*|"
    r"abnormal|too hot|spark\w*|smell\w*|burn\w*|damag\w*|loose|warning light|trip(?:ped|s)?|short circuit)\b",
    re.I,
)
_COMMIT = re.compile(r"\b(i(?:'ll| will| am going to|'m going to| shall)|i promise|i can do)\b", re.I)
_DECISION = re.compile(
    r"\b(we(?:'ll| will| are going to|'re going to| shall| decided| have decided)|let's|let us|from now on|"
    r"starting (?:now|today|tomorrow)|the decision is|we run|we keep|decided to)\b",
    re.I,
)
_PROCEDURE = re.compile(r"^(after|first|once)\b.+?,\s*(then\s+)?\w+|\bthen\b.+\bthen\b|\bstep \d", re.I)
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?;,])\s+")
_COND_STRIP = re.compile(r"\b(?:until|till|unless|before|only if|only after|if)\b[^.!?]*", re.I)
_NEGATED = re.compile(r"\b(?:not|never|yet to)\b|n't\b", re.I)
_EXCEPTION = re.compile(r"\b(can only|may only|only (?:if|when|after)|except)\b", re.I)
_IMPERATIVE_START = re.compile(
    r"^(please\s+)?(" + "|".join(sorted({v.split(' ')[0] for v, _ in _VERB_TO_FAMILY} | {
        "wait", "call", "tell", "report", "wear", "put", "keep", "set", "reduce", "increase", "lower", "raise",
        "remove", "install", "close", "lock", "unlock", "label", "mark", "send", "bring", "take", "measure",
        "record", "write", "follow", "evacuate", "leave", "slow"}, key=len, reverse=True)) + r")\b",
    re.I,
)

HAZARDS: dict[str, tuple[str, str]] = {
    "lockout": ("Lockout/Tagout", "critical"), "tagout": ("Lockout/Tagout", "critical"),
    "loto": ("Lockout/Tagout", "critical"), "lock out": ("Lockout/Tagout", "critical"),
    "lock-out": ("Lockout/Tagout", "critical"), "danger tag": ("Lockout/Tagout", "critical"),
    "high voltage": ("High voltage", "critical"),
    "electric": ("Electrical", "high"), "voltage": ("Electrical", "high"), "live wire": ("Live conductor", "critical"),
    "gas": ("Gas", "high"), "chemical": ("Chemical", "high"), "acid": ("Chemical", "high"),
    "pressure": ("Stored pressure", "high"), "confined space": ("Confined space", "critical"),
    "fire": ("Fire", "critical"), "smoke": ("Smoke / fire", "high"), "hot": ("Hot surface", "medium"),
    "forklift": ("Mobile equipment", "high"), "crane": ("Lifting / suspended load", "high"),
    "fall": ("Fall from height", "high"), "ladder": ("Working at height", "medium"),
    "blade": ("Cutting edge", "high"), "rotating": ("Rotating parts", "high"),
    "emergency": ("Emergency", "critical"), "evacuate": ("Evacuation", "critical"),
    "valve": ("Pressure system", "medium"), "ppe": ("PPE", "medium"), "gloves": ("PPE", "low"),
    "helmet": ("PPE", "low"), "goggles": ("PPE", "low"), "spill": ("Spill", "medium"),
}
_RISK_ORDER = ["none", "low", "medium", "high", "critical"]


@dataclass
class Extraction:
    kind: str
    subject: str = ""
    entities: list[str] = field(default_factory=list)
    action: str = ""
    action_family: str = ""
    polarity: str = "info"
    condition: str = ""
    risk: str = "none"
    hazards: list[str] = field(default_factory=list)
    is_question: bool = False
    explanation: list[str] = field(default_factory=list)


def assess_risk(text: str) -> tuple[str, list[str]]:
    low = text.lower()
    level, found = "none", []
    for term, (label, lvl) in HAZARDS.items():
        if re.search(rf"\b{re.escape(term)}(?:s|es|al|ed|ing)?\b", low):
            if label not in found:
                found.append(label)
            if _RISK_ORDER.index(lvl) > _RISK_ORDER.index(level):
                level = lvl
    return level, found


def _raise(level: str, to: str) -> str:
    return to if _RISK_ORDER.index(to) > _RISK_ORDER.index(level) else level


def extract(text_en: str, source_text: str = "", source_lang: str = "en") -> Extraction:
    t = " ".join(text_en.strip().split())
    why: list[str] = []
    ents = find_entities(t, source_text, source_lang)
    subject = ents[0] if ents else ""
    verb, fam, _ = find_action(t)
    risk, hazards = assess_risk(t)
    cond_m = _COND.search(t)
    condition = f"{cond_m.group(1).lower()} {cond_m.group(2).strip()}" if cond_m else ""
    is_q = t.endswith("?") or bool(_QUESTION_START.match(t)) or source_text.strip().endswith(("?", "？"))
    neg = _NEG.search(t)
    # Judge each sentence/clause separately: "We are behind schedule. Start Machine 4 now." is an order.
    clauses = [c.strip() for c in _CLAUSE_SPLIT.split(t) if c.strip()]
    imperative = any(_REQ.match(c) or _IMPERATIVE_START.match(c) for c in clauses)
    # Completion words inside "until/unless/before ..." describe a condition, not something done.
    main = _COND_STRIP.sub("", t)
    outcome = bool(_OUTCOME.search(main)) and not _NEGATED.search(main)

    if is_q:
        kind, polarity = "question", "info"
        why.append("question form")
    elif _EXCEPTION.search(t) and fam:
        kind, polarity = "exception", "forbid"
        why.append("'only if / can only' → conditional permission")
    elif neg and fam:
        kind, polarity = "instruction", "forbid"
        why.append(f"prohibition '{neg.group(0)}' + action '{verb}'")
    elif outcome:
        kind, polarity = "outcome", "info"
        why.append("completion wording (replaced / fixed / passed ...)")
    elif _COMMIT.search(t):
        kind, polarity = "commitment", "info"
        why.append("first-person promise (I will ...)")
    elif _ISSUE.search(t) and not imperative:
        kind, polarity = "issue", "info"
        why.append(f"problem wording '{_ISSUE.search(t).group(0)}'")
    elif _DECISION.search(t):
        kind, polarity = "decision", ("require" if fam else "info")
        why.append("team decision wording (we will / let's / from now on)")
    elif _PROCEDURE.search(t) and fam:
        kind, polarity = "procedure", "require"
        why.append("ordered steps (after ..., then ...)")
    elif imperative:
        kind, polarity = "instruction", "require"
        why.append("imperative instruction")
    else:
        kind, polarity = "note", "info"

    if kind not in ("instruction", "exception", "commitment", "issue"):
        condition = ""
    if kind in ("instruction", "exception", "procedure") and subject:
        risk = _raise(risk, "medium")
    if kind in ("instruction", "exception") and polarity == "forbid":
        risk = _raise(risk, "high")
        why.append("equipment restriction → high risk")
    if kind == "issue":
        risk = _raise(risk, "medium")

    return Extraction(
        kind=kind, subject=subject, entities=ents, action=verb, action_family=fam, polarity=polarity,
        condition=condition, risk=risk, hazards=hazards, is_question=is_q, explanation=why,
    )


_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "has", "have", "had", "to", "of", "and", "or",
    "on", "in", "at", "for", "with", "it", "this", "that", "until", "unless", "before", "after", "when", "once",
    "now", "just", "already", "we", "i", "you", "they", "please", "do", "not", "don't", "can", "will", "must",
    "machine", "line", "number", "no",
}
_SYN = {
    "replaced": "replace", "replacing": "replace", "changed": "replace", "change": "replace", "swapped": "replace",
    "fixed": "repair", "repaired": "repair", "fix": "repair", "fixing": "repair", "mended": "repair",
    "signed": "sign", "approved": "sign", "completed": "finish", "finished": "finish", "done": "finish",
    "cleaned": "clean", "inspected": "inspect", "checked": "inspect", "check": "inspect",
}


def content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {_SYN.get(w, w) for w in words if w not in _STOP and len(w) > 1}
