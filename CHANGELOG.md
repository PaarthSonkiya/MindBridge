# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — 2026-10-22 (Phase 3 prototype)

### Changed

- Translation picks a model per language pair: envit5 (T5 275M, int8) for English ⇄ Vietnamese,
  NLLB-200 distilled 1.3B (int8) for Korean/Chinese ⇄ Vietnamese, each loaded only when its pair is used.
  Chosen by measurement on the organisers' sample set (`bench/results/published/README.md`).
- Chinese translations use full-width punctuation.
- Benchmark ASR error rates are corpus-level.

### Added

- Benchmark reads the organisers' sample-set layouts (xlsx + wav/<ID>.wav; <Lang>_text / <Lang>_voice).
- `python -m mindbridge file <wav>` and `translate --file` for runs without a microphone.
- Offline package: pinned aarch64 wheels (`requirements-aarch64.lock`), pip bootstrapped without
  python3-venv, only the models the app uses, manifest with sha256 and licences.
- Submission builder for the organisers' template (`docs/submission/`).

## [0.3.0] — 2026-10-22

### Changed

- Complete rebuild for on-device use on the Qualcomm RB3 Gen 2 (QCS6490): Whisper on the Hexagon NPU
  (Qualcomm AI Hub w8a16 builds via onnxruntime-qnn), offline translation and speech synthesis on the CPU,
  rule-based operational memory (conflicts, understanding checks, recall, shift handover), touchscreen UI,
  strict offline guard and benchmark harness with raw logs. No cloud services.

## [0.1.0] — 2026-07-01

### Added

- **Understanding Engine** (FastAPI) with the full edge pipeline:
  - Intent recognition (7 categories)
  - Risk & Safety Intelligence with hazard lexicon and risk levels
  - EN ⇄ VI translation (offline phrase book + optional Claude)
  - Expertise Adaptation Engine (engineer / technician / operator / trainee)
  - **Understanding Score™** comprehension verification with explainable factors
  - Shared Context Memory and AI shift-handover reports
- **Understanding Console** (React + TypeScript) demonstrating the live pipeline.
- Dual-engine design: deterministic offline mode, transparent Claude upgrade.
- Test suite (unit + API integration), Ruff linting, and CI workflow.
- Project documentation: architecture, scoring methodology, roadmap.

[0.1.0]: https://github.com/PaarthSonkiya/MindBridge/releases/tag/v0.1.0
