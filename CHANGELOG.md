# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
