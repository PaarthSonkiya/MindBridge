# Changes since the Phase 2 proposal

For the "brief update on any changes to your team membership or technical direction" field of the
submission form.

**Team:** unchanged.

**Technical direction:** same product (offline voice translation + operational memory on QCS6490),
with these engineering changes made while building on real hardware:

| Phase 2 proposal | Phase 3 prototype | Reason |
|---|---|---|
| ASR: SenseVoice Small | **Whisper large-v3-turbo w8a16** compiled by Qualcomm AI Hub for QCS6490 (Whisper-small as fast mode) | SenseVoice Small does not support Vietnamese. Turbo halves Vietnamese word errors vs Whisper-small on FLEURS (22.9% → 10.9%) and runs fully on the NPU (1.4 s encoder, 18.5 ms/token, measured on RB3 Gen 2) |
| SLM (0.5–1B) for intent and memory extraction | **Deterministic rule engine** on an English pivot | Ready-made LLM runtimes (Genie) do not target QCS6490's HTP v68; on the CPU an SLM adds seconds per turn. Rules are instant, explainable and cannot invent instructions. SLM moves to IQ-8275-class hardware in the roadmap |
| Translation: NLLB-200 distilled | **envit5** (T5 275M) for EN ⇄ VI, **NLLB-200 distilled 1.3B** for KO/ZH ⇄ VI; CTranslate2 int8 on the CPU | Chosen by measurement on the organisers' samples and FLORES: envit5 beats NLLB-1.3B on VI→EN (BLEU 35.0 vs 32.0) and EN→VI (FLORES 42.7 vs 39.5) at a fifth of the size; NLLB-1.3B beats 600M by 2–4 BLEU; 3.3B does not fit in RAM. CPU keeps the NPU dedicated to speech recognition |
| TTS: Piper | **Piper** (vi, en, zh) + **Supertonic-3** (ko) | No Piper Korean voice; Supertonic-3 is far more intelligible in Korean |
| 8 GB RAM target | RB3 Gen 2 has **6 GB**; MindBridge's peak usage is reported in the benchmark logs | Dev-kit spec |
| Wearable badge with e-ink | **Dev kit + HDMI touchscreen**; the badge's e-ink card is reproduced on screen | Form factor is "encouraged", not mandatory; pipeline stability first |
| Crew Mesh sync | Deferred to roadmap | Single-device prototype |
