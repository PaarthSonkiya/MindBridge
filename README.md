<div align="center">

# ◇ MindBridge

### Translating Understanding, Not Just Language

**An AI-powered Communication Operating System that verifies the listener actually understood — not just that the words were translated.**

[![CI](https://github.com/PaarthSonkiya/MindBridge/actions/workflows/ci.yml/badge.svg)](https://github.com/PaarthSonkiya/MindBridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Frontend: React + TS](https://img.shields.io/badge/frontend-React%20%2B%20TypeScript-61dafb.svg)](frontend/)
[![Edge-first](https://img.shields.io/badge/runtime-edge--first%20%E2%80%A2%20offline--capable-6ee7d4.svg)](#-edge-first-by-design)

</div>

---

## The shift: from Translation AI to Understanding AI

Existing tools answer **"Did the system translate the sentence correctly?"**
MindBridge answers the question that actually prevents accidents:

> **"Did the listener actually understand the message?"**

In manufacturing, logistics, construction, healthcare, energy, and mining, communication
fails not only across *languages* but across *expertise, context, and comprehension*. A
correctly translated safety instruction is worthless if the worker didn't grasp it.
MindBridge analyses every message across five dimensions — **intent, context, risk,
expertise, and understanding** — and actively closes comprehension gaps before they
become incidents.

## 🎯 Core innovation — the Understanding Score™

For every safety-critical instruction, MindBridge asks the listener to confirm, then scores
how likely it is they truly understood — from an explainable, weighted breakdown:

| Factor | Weight | What it measures |
|--------|:------:|------------------|
| Key-point coverage | 40% | Did the read-back capture the critical actions? |
| Entity coverage | 25% | Were equipment / part references (e.g. *Filter B*, *LOTO*) retained? |
| Confirmation language | 15% | Did the listener affirm rather than hedge? |
| Conversational clarity | 10% | Absence of confusion / requests to repeat. |
| Contextual consistency | 10% | Did the read-back avoid contradicting the order? |

When the score falls below threshold, MindBridge automatically **rephrases, simplifies,
adds context, or requests clarification** — turning translation into *verified understanding*.

See [`docs/understanding-score.md`](docs/understanding-score.md) for the full methodology.

## ✨ What's in this repository

A working, runnable prototype of the MindBridge engine and console:

- **🧠 Understanding Engine** (`backend/`) — a FastAPI service implementing the full edge
  pipeline: intent recognition → risk intelligence → translation → expertise adaptation →
  comprehension verification → shared context memory → shift handover.
- **🖥️ Understanding Console** (`frontend/`) — a React + TypeScript interface that
  demonstrates the live pipeline, the Understanding Score™ gauge, risk flags, and the AI
  shift-handover report.
- **🔌 Dual engine** — runs **fully offline** on a deterministic, explainable NLP engine
  (perfect for edge devices and reproducible demos), and **transparently upgrades to
  Claude** (`claude-opus-4-8`) when an `ANTHROPIC_API_KEY` is provided.

## 🏗️ Architecture

```
                          ┌──────────────────────────────────────────┐
   Speech / Text  ─────▶  │            UNDERSTANDING ENGINE           │
                          │                                          │
                          │  1. Intent Recognition                   │
                          │  2. Risk & Safety Intelligence           │
                          │  3. Translation  (EN ⇄ VI)               │
                          │  4. Expertise Adaptation                 │
                          │  5. Understanding Verification ◀── score │
                          │  6. Shared Context Memory                │
                          └──────────────────────────────────────────┘
                                 │                          │
                          Adapted, verified           Shift handover
                          message + TTS                  reports
```

Each stage degrades gracefully: with no network and no API key the deterministic engine
keeps every feature working. [`docs/architecture.md`](docs/architecture.md) has the details.

## 🚀 Quick start

You'll need **Python 3.11+** and **Node 18+**.

### 1. Backend (Understanding Engine)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000  (docs at /docs)
```

> The service boots with **zero configuration** in offline mode. To enable Claude-powered
> reasoning, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.

### 2. Frontend (Understanding Console)

```bash
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

The dev server proxies `/api` to the backend automatically. Open the console, pick a
preset message (e.g. *Lockout/Tagout*), run it through the engine, type a worker read-back,
and watch the Understanding Score™ update live.

## 🔬 Try it from the API

```bash
# Analyse an instruction
curl -s localhost:8000/api/process -H 'Content-Type: application/json' -d '{
  "text": "Replace Filter B before restarting the machine.",
  "target_lang": "vi", "listener_expertise": "trainee"
}'

# Score a worker read-back
curl -s localhost:8000/api/verify -H 'Content-Type: application/json' -d '{
  "original_text": "Replace Filter B before restarting the machine.",
  "readback_text": "Understood, I will replace Filter B before restart."
}'
```

## 🧩 Key features

| Feature | Status | Where |
|---------|:------:|-------|
| Real-time multilingual translation (EN ⇄ VI) | ✅ | `engine/translator.py` |
| Intent recognition (7 categories) | ✅ | `engine/intent.py` |
| Expertise adaptation engine | ✅ | `engine/expertise.py` |
| Risk & safety intelligence | ✅ | `engine/risk.py` |
| Comprehension verification — **Understanding Score™** | ✅ | `engine/understanding.py` |
| Shared context memory | ✅ | `memory/context_store.py` |
| AI shift-handover assistant | ✅ | `engine/pipeline.py` |
| Human ↔ machine (IoT) communication | 🔜 | Roadmap Phase 3 |

## 🛡️ Edge-first by design

All core processing is deterministic and runs on-device — no message leaves the machine in
offline mode. This is intended for **Snapdragon-powered edge hardware** where privacy,
latency, and reliability in low-connectivity industrial environments matter most. The
Claude path is an *optional* enhancement, not a dependency.

## 🧪 Tests & quality

```bash
cd backend && pip install -r requirements-dev.txt
pytest            # unit + API integration tests
ruff check .      # linting
```

CI runs the backend test suite and the frontend type-check + build on every push — see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## 🗺️ Roadmap

1. **Phase 1** — Real-time multilingual communication with understanding verification ✅ *(this prototype)*
2. **Phase 2** — Shared team memory & AI shift handovers ✅ *(prototype)*
3. **Phase 3** — Industrial IoT & machine integration
4. **Phase 4** — AR-assisted contextual guidance
5. **Phase 5** — Universal AI Communication Infrastructure

Full detail in [`docs/roadmap.md`](docs/roadmap.md).

## 📂 Project structure

```
MindBridge/
├── backend/        FastAPI Understanding Engine (Python)
├── frontend/       React + TypeScript Understanding Console
├── docs/           Architecture, scoring methodology, roadmap
└── .github/        CI workflow, issue & PR templates
```

## 🤝 Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Issues and pull requests are welcome.

## 📜 License

[MIT](LICENSE) © 2026 Paarth Sonkiya

---

<div align="center">
<em>MindBridge exists to eliminate misunderstandings in the workplace — transforming
communication into verified understanding for safer, smarter collaboration.</em>
</div>
