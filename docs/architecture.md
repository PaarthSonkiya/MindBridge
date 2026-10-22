# Architecture

MindBridge is one Python process on the RB3 Gen 2. It serves a touchscreen UI on `127.0.0.1`,
captures audio from the board's microphone, and runs four models plus a rule engine. No component
opens a network connection; `mindbridge/offline_guard.py` patches the socket layer so any attempt
to reach a non-loopback address fails and is counted (the count is shown in **Run details**).

## Pipeline

```
                  ┌───────────────────────── one conversational turn ─────────────────────────┐
 tap / key ─▶ mic │ high-pass 80 Hz ─▶ Silero VAD trim ─▶ Whisper encoder ─▶ Whisper decoder  │
                  │   (numpy/scipy)      (CPU, 2 MB)        (NPU, 1×)          (NPU, 1×/token) │
                  │                                                │                          │
                  │                                   text in the speaker's language          │
                  │                                                ▼                          │
                  │                              NLLB-200 1.3B (CTranslate2 int8, CPU)         │
                  │                                                ▼                          │
                  │                    text in the listener's language ─▶ UI immediately      │
                  │                                                ▼                          │
                  │                              Piper / Supertonic TTS (CPU) ─▶ speaker      │
                  └────────────────────────────────────────────────────────────────────────────┘
                                   │ (after the translation is shown, off the critical path)
                                   ▼
                     English pivot ─▶ extractor ─▶ memory engine ─▶ alerts · check question · answer
                                                         │
                                                      SQLite (data/memory.db)
```

### Why this split between NPU and CPU

* **Whisper on the NPU.** The encoder is most of Whisper's compute and has fixed shapes
  (128 × 3000 log-mel for large-v3-turbo). Qualcomm AI Hub publishes w8a16 builds compiled for the
  QCS6490's Hexagon v68. Measured on a hosted RB3 Gen 2: turbo 1,402 ms encoder + 18.5 ms per token;
  small 235 ms + 23 ms per token; every layer on the NPU. Turbo is the default because it halves
  Vietnamese word errors on real speech (22.9% → 10.9% on FLEURS). MindBridge drives AI Hub's
  static-shape decoder (200-slot self-attention cache, quantised uint8/uint16 I/O) one token at a
  time from numpy, so no PyTorch is needed on the device.
* **NLLB on the CPU.** Translation is an autoregressive encoder–decoder with variable-length
  input. CTranslate2's int8 kernels run NLLB-1.3B on the Kryo cores while the NPU stays free
  for the next utterance. 1.3B beats 600M by 2–4 BLEU in five of six directions on FLORES.
* **TTS on the CPU.** Piper VITS voices synthesise faster than real time on one or two cores.

### Speech recognition details (`mindbridge/asr/`)

* `mel.py` — Whisper log-mel in numpy, verified equal to `transformers.WhisperFeatureExtractor`
  (max difference 1e-7).
* `whisper_qnn.py` — runs AI Hub's encoder/decoder pair (quantised I/O read from AI Hub's
  `metadata.json`) on the NPU through
  `onnxruntime-qnn` (plugin EP, HTP backend, CPU fallback disabled so nothing silently runs on
  the CPU). The prompt is forced to `<|sot|><|lang|><|transcribe|><|notimestamps|>`: push-to-talk
  already knows who is speaking, so the language is never guessed wrongly. When it must be
  detected, only the conversation's two languages are considered. A loop guard stops Whisper's
  repetition hallucinations.
* `whisper_ct2.py` — CPU fallback (Whisper-small, CTranslate2 int8). Both paths share the numpy
  features and a byte-level detokenizer, so Chinese/Korean characters split across tokens survive.
* Chinese output is converted to Simplified (OpenCC) to match `zho_Hans`.

### Memory layer (`mindbridge/memory/`)

Every utterance is reduced to an English pivot (the English side of the pair, or one extra NLLB
call for VI⇄KO and VI⇄ZH) and passed to a deterministic extractor that recognises:

| Kind | Example | What MindBridge does |
|---|---|---|
| instruction (forbid) | "Do not restart Machine 4 until the valve is replaced." | stores a restriction with its condition; asks the listener a check question; badge shows **MACHINE 4 / DO NOT RESTART** |
| instruction (require) | "Start Machine 4." | if it contradicts an active restriction: red conflict alert in both languages, order held |
| exception | "Machine 4 can only restart if maintenance signs off." | conditional restriction |
| issue | "Machine 6 is vibrating again." | amber alert, open issue |
| commitment | "I will replace the valve before night shift." | tracked until an outcome clears it |
| decision / procedure | "We will run Line 2 at half speed." | kept for the handover |
| outcome | "The valve was replaced and Machine 4 passed the test." | clears matching restrictions, issues and commitments |
| question | "Can we restart Machine 4?" | answered from memory, in the asker's language |

Equipment is recognised in English ("machine number four" → Machine 4) and directly in the
source language ("máy số 4", "4번 기계", "四号机器"). Small talk is never stored.

Rules instead of a language model: on the QCS6490 a 0.5–1B model would compete with Whisper
for the NPU or add seconds on the CPU, and a rule engine cannot invent an instruction nobody gave.
The roadmap moves extraction to a small LLM on IQ-8275/IQ-9075-class hardware.

## Process layout

```
python -m mindbridge serve
 ├─ uvicorn (asyncio)  ── HTTP + WebSocket on 127.0.0.1:8765 ── kiosk browser on HDMI
 ├─ worker thread      ── one job at a time: talk / ask / verify
 ├─ PortAudio callback ── mic blocks → VAD end-pointing → auto-stop
 └─ SQLite             ── data/memory.db (memories + event log)
```

If PortAudio is missing, the UI records through the browser (`getUserMedia` on localhost) and
uploads a WAV; the rest of the pipeline is unchanged.

## Failure behaviour

| Failure | Behaviour |
|---|---|
| NPU unavailable / QNN load error | Whisper runs on the CPU; UI chip shows "Speech on CPU" with the reason |
| TTS voice missing | Text-only output |
| Nothing recognised | "Didn't catch that" prompt; nothing stored |
| Network present | Allowed but never used; UI warns "Network is on — turn it off for the demo" |
