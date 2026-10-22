# Changes since the Phase 2 proposal

For the "brief update on any changes to your team membership or technical direction" field of the
submission form.

**Team:** unchanged.

**Technical direction:** same product (offline voice translation + operational memory on QCS6490),
with these engineering changes made while building on real hardware:

| Phase 2 proposal | Phase 3 prototype | Reason |
|---|---|---|
| ASR: SenseVoice Small | **Whisper-small w8a16** compiled by Qualcomm AI Hub for QCS6490 | SenseVoice Small does not support Vietnamese; Whisper does, and AI Hub ships an NPU-optimised build for this chip |
| SLM (0.5–1B) for intent and memory extraction | **Deterministic rule engine** on an English pivot | Ready-made LLM runtimes (Genie) do not target QCS6490's HTP v68; on the CPU an SLM adds seconds per turn. Rules are instant, explainable and cannot invent instructions. SLM moves to IQ-8275-class hardware in the roadmap |
| Translation: NLLB-200 distilled | **NLLB-200 distilled 600M**, CTranslate2 int8 on the CPU | Kept; runs on the CPU so the NPU stays dedicated to speech recognition |
| TTS: Piper | **Piper** (vi, en, zh) + **Supertonic-3** (ko) | No Piper Korean voice; Supertonic-3 is far more intelligible in Korean |
| 8 GB RAM target | RB3 Gen 2 has **6 GB**; MindBridge's peak usage is reported in the benchmark logs | Dev-kit spec |
| Wearable badge with e-ink | **Dev kit + HDMI touchscreen**; the badge's e-ink card is reproduced on screen | Form factor is "encouraged", not mandatory; pipeline stability first |
| Crew Mesh sync | Deferred to roadmap | Single-device prototype |
