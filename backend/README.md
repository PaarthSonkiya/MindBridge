# MindBridge Backend — Understanding Engine

FastAPI service implementing the MindBridge Edge AI pipeline. It runs **fully
offline** with a deterministic, explainable heuristic engine, and transparently
upgrades to **Claude-powered reasoning** when `ANTHROPIC_API_KEY` is set.

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for interactive API documentation.

## Endpoints

| Method | Path            | Purpose                                                |
|--------|-----------------|--------------------------------------------------------|
| GET    | `/api/health`   | Service + engine status.                               |
| POST   | `/api/process`  | Intent → risk → translation → expertise adaptation.    |
| POST   | `/api/verify`   | Understanding Score™ from a listener read-back.        |
| POST   | `/api/handover` | AI shift-handover report for a session.                |

## Architecture

```
app/
├── main.py              FastAPI routes
├── config.py            Env-driven settings (zero-config defaults)
├── models/schemas.py    Public request/response contracts
├── engine/
│   ├── pipeline.py      Orchestrates every stage (offline ⇄ Claude)
│   ├── intent.py        Intent recognition
│   ├── risk.py          Risk & Safety Intelligence
│   ├── translator.py    EN↔VI translation
│   ├── expertise.py     Expertise Adaptation Engine
│   ├── understanding.py Understanding Score™
│   └── lexicon.py       Industrial domain knowledge
├── memory/context_store.py  Shared Context Memory
└── llm/client.py        Optional Claude client
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
