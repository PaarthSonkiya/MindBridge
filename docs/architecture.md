# Architecture

MindBridge is built as an **edge-first pipeline** with an optional cloud-reasoning upgrade.
Every stage is designed to produce a useful result with no network connection, then
transparently improve when Claude is available.

## The pipeline

```
Speech / Text input
        │
        ▼
┌───────────────────┐
│ 1. Intent         │  Classify purpose: instruction · warning · question ·
│    Recognition    │  confirmation · emergency · approval · escalation.
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 2. Risk & Safety  │  Detect hazards (LOTO, high voltage, gas, confined space…)
│    Intelligence   │  and assign a risk level; flag for mandatory read-back.
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 3. Translation    │  EN ⇄ VI. Offline phrase book + honest fallback, or
│                   │  full Claude translation that preserves safety detail.
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 4. Expertise      │  Re-express for engineer / technician / operator / trainee,
│    Adaptation     │  expanding jargon via the technical glossary.
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 5. Understanding  │  Score a listener read-back against the original to
│    Verification   │  estimate true comprehension → Understanding Score™.
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 6. Shared Context │  Persist turns, equipment references, risk events; power
│    Memory         │  continuity and the AI shift-handover report.
└───────────────────┘
```

## Components

| Module | Responsibility |
|--------|----------------|
| `app/main.py` | FastAPI routes (`/process`, `/verify`, `/handover`, `/health`). |
| `app/engine/pipeline.py` | Orchestrates all stages; routes between offline and Claude. |
| `app/engine/intent.py` | Ordered keyword-cue intent classifier. |
| `app/engine/risk.py` | Hazard lexicon → risk level + confirmation requirement. |
| `app/engine/translator.py` | Offline EN⇄VI phrase book with labelled fallback. |
| `app/engine/expertise.py` | Expertise-level rewriting + key-point extraction. |
| `app/engine/understanding.py` | Weighted, explainable Understanding Score™. |
| `app/engine/lexicon.py` | Domain knowledge: hazards, glossary, phrase book. |
| `app/memory/context_store.py` | Thread-safe in-process session memory. |
| `app/llm/client.py` | Optional Claude client (lazy, dependency-isolated). |

## Dual-engine routing

`UnderstandingEngine` checks `Settings.llm_enabled` (true only when an API key is present
and offline mode is not forced). Claude-backed methods are wrapped in try/except so any
failure — missing package, network error, malformed reply — **falls back to the deterministic
engine** rather than failing the request. This keeps the system dependable on the factory
floor.

## Why edge-first

Industrial environments have intermittent connectivity, strict data-privacy requirements,
and zero tolerance for latency on safety messages. By making the deterministic engine the
*default* rather than a fallback, MindBridge guarantees that intent, risk flagging, and
comprehension scoring keep working even when fully air-gapped — the design target being
Snapdragon-class on-device NPUs.

## Scaling the memory layer

`ContextStore` is an in-process store behind a small interface (`add_turn`, `get`,
`recent_context`, `equipment_referenced`). A production deployment swaps it for SQLite
(single edge device) or Redis/Postgres (multi-node site) without touching the engine.
