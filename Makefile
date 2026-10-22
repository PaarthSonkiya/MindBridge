# MindBridge — convenience targets.
.PHONY: help install models serve talk doctor test lint bench-text bench-voice profile bundle

help:
	@echo "make install      Python env + dependencies (.venv)"
	@echo "make models       Download/convert all models (online, once)"
	@echo "make serve        Run the device UI on http://127.0.0.1:8765"
	@echo "make talk         Terminal push-to-talk"
	@echo "make doctor       Check models, NPU, audio, network"
	@echo "make test         Unit tests (no models needed)"
	@echo "make bench-text   Translation quality on DATA=<dataset>"
	@echo "make bench-voice  Full voice pipeline benchmark on DATA=<dataset>"
	@echo "make profile      Qualcomm AI Hub on-device profile (needs QAI_HUB_API_TOKEN)"
	@echo "make bundle       Build the offline installation bundle for judges"

install:
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

models:
	. .venv/bin/activate && python scripts/fetch_models.py

serve:
	bash scripts/run.sh

talk:
	. .venv/bin/activate && python -m mindbridge talk

doctor:
	. .venv/bin/activate && python -m mindbridge doctor --run

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check mindbridge tests bench qualcomm scripts

bench-text:
	. .venv/bin/activate && python bench/run_benchmark.py --data $(DATA) --mode text

bench-voice:
	. .venv/bin/activate && python bench/run_benchmark.py --data $(DATA) --mode voice --require-offline

profile:
	. .venv/bin/activate && python qualcomm/aihub_profile.py

bundle:
	bash scripts/build_offline_bundle.sh
