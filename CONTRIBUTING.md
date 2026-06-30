# Contributing to MindBridge

Thanks for your interest in MindBridge! This guide covers how to get set up and the
conventions we follow.

## Development setup

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Frontend
cd ../frontend
npm install
```

## Before opening a pull request

Run the same checks CI runs:

```bash
# Backend
cd backend
ruff check app tests
MINDBRIDGE_FORCE_OFFLINE=true pytest -q

# Frontend
cd ../frontend
npm run build
```

## Conventions

- **Python** — formatted and linted with [Ruff](https://docs.astral.sh/ruff/); type hints
  on public functions; keep the offline engine deterministic and explainable.
- **TypeScript** — `strict` mode; no `any` in new code.
- **Engine changes** — every scoring or classification change should ship with a test.
- **Commits** — present-tense, imperative summaries ("Add risk detection for hot work").

## Project layout

| Area | Path | Notes |
|------|------|-------|
| Pipeline orchestration | `backend/app/engine/pipeline.py` | Offline ⇄ Claude routing |
| Scoring logic | `backend/app/engine/understanding.py` | The Understanding Score™ |
| Domain knowledge | `backend/app/engine/lexicon.py` | Hazards, glossary, phrase book |
| API contract | `backend/app/models/schemas.py` | Pydantic schemas |
| UI | `frontend/src/` | React + TypeScript |

## Reporting issues

Use the issue templates under `.github/ISSUE_TEMPLATE/`. For anything security-related,
please follow [`SECURITY.md`](SECURITY.md) instead of opening a public issue.
