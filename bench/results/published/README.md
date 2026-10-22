# Published measurements

Everything here was measured, not estimated. Raw files sit next to this page.

## 1. NPU performance on a real RB3 Gen 2 (Qualcomm AI Hub, hosted device)

Profile jobs on a **Dragonwing RB3 Gen 2 Vision Kit (QCS6490, Hexagon v68)**, `qualcomm/aihub_profile.py`,
10 iterations, the exact context binaries MindBridge ships.

| Model (w8a16, AI Hub) | Part | On-device latency | Peak memory | Layers on NPU | AI Hub job |
|---|---|---|---|---|---|
| Whisper large-v3-turbo (default) | encoder (per utterance) | **1,402 ms** | 21.9 MB | 6,314 / 6,314 | [jpvm60vrp](https://workbench.aihub.qualcomm.com/jobs/jpvm60vrp/) |
| Whisper large-v3-turbo (default) | decoder (per token) | **18.5 ms** | 37.9 MB | 1,533 / 1,533 | [jgow2k3kp](https://workbench.aihub.qualcomm.com/jobs/jgow2k3kp/) |
| Whisper small (fast mode) | encoder (per utterance) | **235 ms** | 32.1 MB | 1,894 / 1,894 | [j57ny029p](https://workbench.aihub.qualcomm.com/jobs/j57ny029p/) |
| Whisper small (fast mode) | decoder (per token) | **23.3 ms** | 69.3 MB | 2,853 / 2,853 | [jp114y27p](https://workbench.aihub.qualcomm.com/jobs/jp114y27p/) |

A 20-token sentence: turbo ≈ 1.4 s + 20 × 18.5 ms ≈ **1.8 s**; small ≈ 0.24 s + 20 × 23 ms ≈ **0.7 s**.
Folders: `aihub_whisper_turbo_qcs6490/`, `aihub_whisper_small_qcs6490/`.

## 2. MindBridge's decoder on the real NPU

`qualcomm/aihub_validate_whisper.py` runs MindBridge's own decoding loop (quantised I/O, KV cache,
attention mask, forced prompt) with every encoder/decoder call executed as an AI Hub inference job on
the hosted RB3 Gen 2. On an English test clip the NPU predicted `<|en|>` → `<|transcribe|>` →
`<|notimestamps|>` → "Do not restart …", matching the spoken sentence. Log: `aihub_validate_whisper.json`.

## 3. Speech recognition accuracy (real human speech)

Google FLEURS test recordings (read FLORES sentences), 30 utterances per language, CTranslate2 int8 on CPU
(same weights as the NPU builds; the w8a16 NPU builds are Qualcomm's quantisation of these models).

| Model | Vietnamese WER | English WER | Korean CER | Chinese CER |
|---|---|---|---|---|
| Whisper small | 22.9 % | 6.0 % | 10.9 % | 12.6 % |
| **Whisper large-v3-turbo** | **10.9 %** | **4.5 %** | **9.5 %** | **10.5 %** |

File: `asr_fleurs_small_vs_turbo.json`. → Turbo is the default on the NPU.

## 4. Translation model choice (FLORES-200 devtest, 200 sentences per direction)

BLEU / chrF++ (sacreBLEU; `zh` tokenizer for Chinese, character tokens for Korean).

| Direction | NLLB 600M, beam 2 | **NLLB 1.3B, beam 2** | NLLB 600M, greedy |
|---|---|---|---|
| VI→EN | 34.5 / 58.8 | **38.2 / 61.3** | 33.8 / 58.3 |
| EN→VI | 37.7 / 56.6 | **39.5 / 58.1** | 36.4 / 55.6 |
| VI→KO | 31.4 / 25.1 | **34.1 / 27.5** | 29.9 / 24.1 |
| KO→VI | 22.8 / 44.5 | **25.1 / 47.0** | 21.3 / 43.1 |
| VI→ZH | 24.5 / 18.3 | 23.2 / 18.4 | 24.0 / 18.0 |
| ZH→VI | 23.4 / 44.9 | **26.7 / 47.7** | 22.5 / 44.1 |

File: `mt_flores_nllb_size_beam.json`. → NLLB-1.3B, beam 2 is the default.

## Caveats

* Accuracy numbers (3, 4) were run on an x86 CPU; they do not depend on the hardware. Latency and memory
  for the QCS6490 come from section 1 and, for the full app, from `bench/run_benchmark.py` on the board.
* FLORES/FLEURS are general-domain (news, Wikipedia). Factory speech has more numbers and part names.
