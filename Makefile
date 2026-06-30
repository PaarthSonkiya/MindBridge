# MindBridge — developer convenience targets.
.PHONY: help backend-install backend-run test lint frontend-install frontend-run frontend-build dev

help:
	@echo "MindBridge targets:"
	@echo "  make backend-install   Install backend deps into backend/.venv"
	@echo "  make backend-run       Run the Understanding Engine (port 8000)"
	@echo "  make test              Run backend tests (offline mode)"
	@echo "  make lint              Ruff lint the backend"
	@echo "  make frontend-install  Install frontend deps"
	@echo "  make frontend-run      Run the Understanding Console (port 5173)"
	@echo "  make frontend-build    Type-check and build the frontend"

backend-install:
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

backend-run:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload

test:
	cd backend && . .venv/bin/activate && MINDBRIDGE_FORCE_OFFLINE=true pytest -q

lint:
	cd backend && . .venv/bin/activate && ruff check app tests

frontend-install:
	cd frontend && npm install

frontend-run:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
