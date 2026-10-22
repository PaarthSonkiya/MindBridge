# MindBridge

**Offline voice translation and operational memory for multilingual factory floors, running entirely on a Qualcomm QCS6490 (RB3 Gen 2).**

A Korean, Chinese or English supervisor and a Vietnamese operator each tap their side of the
screen and talk. MindBridge recognises the speech on the Hexagon NPU, translates it on the device,
speaks the translation aloud, and remembers what matters for safety: it catches a contradicting
order ("start Machine 4" while a restriction is still active), checks that the operator understood,
answers "can we restart Machine 4?" from the factory's own history, and writes the shift handover.
Nothing leaves the device. The network can be switched off; at run time MindBridge blocks every
outbound connection anyway.

Built for the [OneVoice AI Challenge 2026](https://luma.com/g1rwi7ag) (Phase 3 prototype), with
Qualcomm AI Hub and ONNX Runtime QNN.

## How it works

```
 mic ─▶ high-pass + Silero VAD ─▶ Whisper turbo w8a16 ─▶ envit5 (EN⇄VI)    ─▶ Piper / Supertonic ─▶ speaker
          (CPU)                    (Hexagon NPU,            NLLB-200 1.3B        (CPU)
                                    AI Hub, QNN)            (KO/ZH⇄VI)
                                                            CTranslate2 int8, CPU
                                          │
                                          └─▶ English pivot ─▶ operational memory (rules + SQLite)
                                                                 conflict · verify · recall · handover
```

| Stage | Model | Runs on | Why |
|---|---|---|---|
| Voice activity | Silero VAD v5 | CPU | 2 MB, trims noise, auto-stops recording |
| Speech recognition | Whisper large-v3-turbo, w8a16, compiled by Qualcomm AI Hub for QCS6490 (Whisper-small as fast mode) | **Hexagon NPU** (onnxruntime-qnn) | Heaviest model; fixed shapes suit the NPU. Measured on RB3 Gen 2: 1.4 s encoder + 18.5 ms/token, every layer on the NPU |
| Translation, EN ⇄ VI | VietAI envit5-translation (T5, 275M), CTranslate2 int8 | Kryo CPU | Beats NLLB-1.3B on the organisers' VI→EN samples (BLEU 35.0 vs 32.0) and on FLORES EN→VI (42.7 vs 39.5), at a fifth of the size and several times the speed |
| Translation, KO/ZH ⇄ VI | NLLB-200 distilled 1.3B, CTranslate2 int8 | Kryo CPU | Strongest model that fits the 6 GB board (3.3B needs 4.6 GB on its own); loaded only for these pairs |
| Speech synthesis | Piper VITS (vi, en, zh), Supertonic-3 (ko) | Kryo CPU | Small, natural, offline |
| Memory | Deterministic extractor + SQLite | CPU | Explainable, <1 ms, never invents an instruction |

If the NPU is not available, speech recognition falls back to the CPU automatically
(Whisper-small on CTranslate2, int8) and the UI says so.

### Measured on the organisers' sample set

| Direction | Text in: BLEU / chrF++ | Voice in: BLEU | Speech recognition error |
|---|---|---|---|
| VI→EN | 35.1 / 54.5 | 29.6 | 7.6 % WER |
| VI→KO | 33.2 / 29.0 | 30.7 | 4.6 % WER |
| KO→VI | 19.3 / 37.7 | 18.2 | 7.2 % CER |
| VI→ZH | 40.8 / 30.7 | 38.4 | 16.3 % WER |
| ZH→VI | 27.8 / 50.1 | 27.3 | 3.7 % CER |

On the RB3 Gen 2's NPU (Qualcomm AI Hub profile): Whisper turbo encoder 1.4 s per utterance + 18.5 ms per
token. Every number, raw log and per-sentence output, plus FLEURS/FLORES model comparisons:
[bench/results/published/](bench/results/published/README.md).

Language pairs: **VI ⇄ EN**, **VI ⇄ KO**, **VI ⇄ ZH** (choose on the screen).

## For judges: install offline on an RB3 Gen 2

Ubuntu 24.04 on the RB3 Gen 2 with Python 3.12. Download the offline bundle linked in our
submission, copy it to the board, switch the network off, then:

```bash
tar -xzf mindbridge-offline-0.4.0-aarch64.tar.gz
cd mindbridge-offline-0.4.0-aarch64
bash install_offline.sh          # installs from bundled wheels, verifies model checksums
cd app && bash scripts/run.sh    # opens the UI full-screen on the HDMI display
```

Then tap **Tap to speak** (or press `1` / `2` on a keyboard), speak, and wait for the
translation. **Run details** (top right) shows where each model runs, model sizes, memory use and the
live network state. Full steps, including a Docker option: [docs/reproduction.md](docs/reproduction.md).

## For developers

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/fetch_models.py             # online, once: all models into models/
python -m mindbridge doctor --run          # checks models, NPU, audio, network, translates one line
python -m mindbridge serve                 # http://127.0.0.1:8765
pytest -q                                  # unit tests, no models needed
```

On the board, `bash scripts/setup_rb3.sh` does the system packages, Python environment and models.

## Measuring it

```bash
python bench/run_benchmark.py --data <sample-dataset-folder> --mode text           # BLEU / chrF++
python bench/run_benchmark.py --data <sample-dataset-folder> --mode voice --require-offline
python qualcomm/aihub_profile.py                                                    # on-device NPU profile via AI Hub
```

Each run writes `bench/results/<timestamp>/` with per-sentence results, a summary table, and a
`run.log` containing the device, model inventory and the network state before and after the run.
Published results live in [bench/results/published/](bench/results/published/).

## Repository

```
mindbridge/        the application (pipeline, ASR/MT/TTS backends, memory, server, UI)
  asr/             Whisper on NPU (QNN) and CPU, numpy log-mel, detokenizer
  mt/              envit5 + NLLB on CTranslate2, per-pair router, sentence splitting, phrase cache
  memory/          operational memory objects, extractor, engine, SQLite store
  ui/              offline touchscreen UI (plain HTML/CSS/JS, bundled fonts)
bench/             benchmark harness
qualcomm/          AI Hub fetch + profiling scripts
scripts/           model download, RB3 setup, offline bundle, installer, launcher
docker/            arm64 Dockerfile
docs/              architecture, reproduction, demo scenario, hardware, roadmap, submission draft
tests/             unit tests with fake models
```

## Model licences

Whisper (MIT; Qualcomm AI Hub builds under the AI Hub Models licence), Silero VAD (MIT), Supertonic-3 (MIT), Piper voices (see each model card),
envit5-translation (OpenRAIL, VietAI), NLLB-200 (CC-BY-NC-4.0, non-commercial; a commercial release would swap in a permissively
licensed translation model). Full list with checksums: `models/manifest.json` after download.

## Licence

Code: [MIT](LICENSE) © 2026 Paarth Sonkiya
