# MindBridge: Prototype Submission (Phase 3) — DRAFT

> Working draft to paste into the organisers' *Prototype Submission Template* once we have it as .docx.
> Items marked **[TO FILL]** need numbers or links from the real device run. Never fill them with estimates.
> Final file name: `MindBridge_Prototype Submission_V3.pdf`

## 1. Team and solution

**Team:** MindBridge. Sonkiya Paarth (lead), NTU School of EEE, Singapore. **[TO FILL: other members]**

**Solution in one paragraph.** MindBridge is an offline voice translator and operational-memory device
for multilingual factory floors, running entirely on a Qualcomm QCS6490 (RB3 Gen 2). A supervisor and a
Vietnamese operator each tap their side and talk; MindBridge recognises speech on the Hexagon NPU,
translates on the device, speaks the translation, and remembers what matters for safety. It warns
when a new order contradicts an active restriction, checks that the listener understood, answers
questions such as "can we restart Machine 4?" from the factory's own history, and produces the shift
handover. No audio or text leaves the device.

**Use context (from Phase 2):** foreign-invested electronics and manufacturing plants in Vietnam;
Korean, Chinese and English-speaking supervisors with Vietnamese line operators; noisy, RF-restricted floors.

**Registered pairs tested:** VI ⇄ EN (primary), VI ⇄ KO, VI ⇄ ZH.

## 2. Changes since Phase 2

See `docs/changes_since_phase2.md`. Summary: ASR moved from SenseVoice Small (no Vietnamese) to
Whisper-small compiled by Qualcomm AI Hub for QCS6490; memory extraction moved from an SLM to a
deterministic rule engine (no LLM runtime for HTP v68; keeps latency low); Korean speech output uses
Supertonic-3; badge form factor deferred, its e-ink card is shown on screen. Team unchanged.

## 3. Architecture and hardware

| Stage | Model | Precision | Runs on | Size |
|---|---|---|---|---|
| Voice activity | Silero VAD v5 | fp32 | CPU | **[TO FILL from Run details]** |
| Speech recognition | Whisper-small (Qualcomm AI Hub) | w8a16 | Hexagon NPU (QNN HTP, onnxruntime-qnn 2.7) | **[TO FILL]** |
| Translation | NLLB-200 distilled 600M (CTranslate2) | int8 | Kryo CPU | **[TO FILL]** |
| Speech synthesis | Piper VITS (vi/en/zh), Supertonic-3 (ko) | fp32 / int8 | Kryo CPU | **[TO FILL]** |
| Memory | Rule engine + SQLite | — | CPU | — |

Hardware: Qualcomm RB3 Gen 2 Core Kit (QCS6490, 6 GB RAM), Ubuntu 24.04, HDMI touchscreen,
**[TO FILL: USB mic/speakerphone model]**. Diagram: `docs/architecture.md`.

**Qualcomm software used:** Qualcomm AI Hub (model export for QCS6490 and on-device profiling of the
NPU models on hosted devices), ONNX Runtime QNN execution provider (QAIRT 2.51, HTP backend) on the device.

## 4. Benchmark results (measured offline)

Paste `bench/results/<run>/summary.md` here. Attach `run.log` and `results.jsonl`.

| Direction | N | BLEU | chrF++ | ASR WER/CER | Speech→translation p50 | Total p90 |
|---|---|---|---|---|---|---|
| VI→EN | **[TO FILL]** | | | | | |
| EN→VI | | | | | | |
| VI→KO / KO→VI | | | | | | |
| VI→ZH / ZH→VI | | | | | | |

On-device NPU profile (Qualcomm AI Hub, QCS6490): paste `bench/results/aihub/summary.md` **[TO FILL]**.

Peak RAM during the voice run: **[TO FILL]** MB. Total model size on disk: **[TO FILL]** MB.

## 5. Device integration and UX

* Two big push-to-talk buttons in each speaker's language; keyboard keys `1`/`2` or a USB clicker as
  physical buttons; recording stops automatically on silence.
* Translation shown large and spoken aloud; original shown small for the speaker to confirm.
* Safety light (green / amber / red) and a badge-style e-ink card showing the active restriction.
* Understanding check: after a safety instruction the listener is asked a short question in their
  language and answers by voice.
* Conflict alerts in both languages when an order contradicts an active restriction.
* "Ask about the line" and "Shift handover" for supervisors and the next shift.
* Per-turn latency bar and a **Run details** panel (models, NPU/CPU, sizes, memory, network state).

Designed for factory, construction and warehouse workers: large targets for gloved hands, high-contrast
safety colours, no reading required to start talking.

## 6. Demo package

| Item | Link |
|---|---|
| End-to-end demo video (offline, unedited) | **[TO FILL]** |
| Offline installation bundle (`mindbridge-offline-0.3.0-aarch64.tar.gz`, sha256 in release) | **[TO FILL]** |
| Source code | https://github.com/PaarthSonkiya/MindBridge |
| Benchmark results and logs | **[TO FILL: folder link]** |
| Reproduction guide | `docs/reproduction.md` |

Minimum hardware: aarch64 Linux (glibc ≥ 2.34), Python 3.12, **[TO FILL: measured peak RAM + margin]**
RAM, **[TO FILL]** disk. NPU acceleration requires a QCS6490 with FastRPC (RB3 Gen 2); otherwise
speech recognition runs on the CPU automatically.

## 7. Limitations and roadmap

See `docs/roadmap.md`.
