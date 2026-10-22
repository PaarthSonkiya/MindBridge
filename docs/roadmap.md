# Roadmap and current limitations

## What the Phase 3 prototype does

* Voice-to-voice translation VI⇄EN, VI⇄KO, VI⇄ZH, fully on the RB3 Gen 2.
* Whisper-small on the Hexagon NPU (Qualcomm AI Hub, w8a16); translation and speech on the CPU.
* Operational memory: restrictions with conditions, conflict alerts, understanding checks,
  recall answers, issue tracking, automatic shift handover, a badge-style task card.
* Strict offline mode, benchmark harness with raw logs, offline installer.

## Known limitations (honest list for judges)

* **Translation model licence.** NLLB-200 is CC-BY-NC-4.0: fine for this non-commercial prototype,
  to be replaced before any commercial pilot.
* **Translation runs on the CPU.** NLLB is not yet compiled for the NPU.
* **Speaker separation.** Push-to-talk decides who is speaking; overlapping speech is not separated.
* **Code-switching.** Whisper is forced to the speaker's language per turn; mixed-language
  sentences are transcribed in that language only.
* **Memory extraction is rule-based.** Robust for direct operational phrasing; unusual
  phrasing may be stored as a note instead of an instruction.
* **Crew Mesh** (device-to-device memory sync) is designed, not built.
* **Form factor.** Dev kit + HDMI screen, not yet the badge described in Phase 2.

## Next

| Step | What | Hardware |
|---|---|---|
| 1 | Domain glossary for ASR biasing (machine names, part codes) via Whisper prompt tokens | QCS6490 |
| 2 | Compile the NLLB encoder for the NPU with AI Hub; keep the decoder on the CPU | QCS6490 |
| 3 | Small LLM (Qwen3-1.7B, Genie w4a16) for memory extraction and answers | IQ-8275 / IQ-9075 |
| 4 | Crew Mesh: BLE/Wi-Fi Direct sync of safety restrictions between badges | any |
| 5 | Badge form factor: e-ink 2.13", 3-mic array with beamforming, 4,500 mAh, IP54 | QCS6490 SoM |
| 6 | Pilot at a Korean-owned plant in Vietnam (VI⇄KO) | — |
