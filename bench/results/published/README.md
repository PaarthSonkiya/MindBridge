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
the hosted RB3 Gen 2 (Whisper-small w8a16 context binaries). Input: an English clip of
"Do not restart machine 4 until the pressure valve is replaced."

Real-NPU output, token by token: `<|en|>` → `<|transcribe|>` → `<|notimestamps|>` → **"Do not restart
machine 4 until the pressure valve is replaced"** (exact). Every step's AI Hub job link is in
`aihub_validate_whisper.json`. (The run stopped at a 90-minute limit before the final end-of-text step;
each step waits for a free device in Qualcomm's farm.)

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

## 5. Translator choice on the organisers' sample set (text in, text out)

`bench/compare_mt.py`, organisers' OneVoice samples, sacreBLEU (character tokens for Korean), CPU seconds
per sentence with batch 1 on our 2-core x86 test box (relative speed only).

| Translator | VI→EN (n=100) | VI→KO (n=180) | KO→VI (n=180) | s / sentence |
|---|---|---|---|---|
| **envit5 (T5 275M) int8, greedy** | **34.97 / 54.5** | — (EN⇄VI only) | — | 0.26 (VI→EN) |
| **NLLB-200 1.3B int8, beam 2** | 32.04 / 50.9 | **32.59 / 28.3** | **19.33 / 37.7** | 0.9–1.7 |
| NLLB-200 1.3B, beam 4 | | 32.11 / 27.8 | 19.33 / 37.7 | ≈1.0 |
| NLLB-200 1.3B via English | | 26.03 / 22.7 | 17.10 / 36.0 | ≈2.0 |
| envit5 + NLLB via English | | 23.98 / 20.9 | 15.43 / 35.0 | ≈1.2 |
| NLLB-200 3.3B int8 | not scored: needs 4.6 GB RAM alone, too much for the 6 GB board | | | |

BLEU / chrF++. On FLORES-200 (200 sentences) envit5 scores VI→EN 38.3 / 62.2 and EN→VI 42.7 / 60.7, against
NLLB-1.3B's 38.2 / 61.3 and 39.5 / 58.1. → **envit5 for English ⇄ Vietnamese; NLLB-200 1.3B, beam 2,
direct, for Korean/Chinese ⇄ Vietnamese.** Every hypothesis is in `mt_compare_sample.json`.

## 6. Model sizes

`model_sizes.json` (`bench/model_sizes.py`): 1,405 MB of models loaded for a VI ⇄ EN conversation
(Whisper turbo QNN 984, envit5 266, two Piper voices 155, VAD 0.6); 2,807 MB for VI ⇄ KO (adds NLLB-1.3B
1,341 and Supertonic 139); 3,754 MB for everything shipped, including the CPU fallback and fast mode.

## 7. Organisers' sample set: MindBridge as shipped

`bench/run_benchmark.py` on the OneVoice sample folders (Vie-Eng, Vie-Kor, Vie-Man), offline, the app's
own translators and post-processing, x86-64 CPU (accuracy only; device timing comes from the board).

**Text in, text out** (`onevoice_sample_text/`; BLEU / chrF++, sacreBLEU 13a, `zh` tokens for Chinese,
characters for Korean):

| Direction | N | BLEU | chrF++ | Translator |
|---|---|---|---|---|
| VI→EN | 100 | 35.09 | 54.5 | envit5 |
| VI→KO | 180 | 33.22 | 29.0 | NLLB-1.3B |
| KO→VI | 180 | 19.33 | 37.7 | NLLB-1.3B |
| VI→ZH | 180 | 40.77 | 30.7 | NLLB-1.3B |
| ZH→VI | 180 | 27.83 | 50.1 | NLLB-1.3B |

Two output fixes found on these samples and kept in the app: Chinese translations use full-width
punctuation (VI→ZH 32.8 → 40.8 BLEU), and every translation keeps the source sentence's final punctuation
(VI→KO 32.6 → 33.2). EN→VI cannot be scored: the 100 `EV-*.wav` recordings came with the VI→EN sheet
instead of their own texts.

**Voice in** (recordings → Whisper large-v3-turbo → translation): see `onevoice_sample_voice*/`
(summary.md in each). The CPU run uses turbo's int8 CTranslate2 weights; the board runs Qualcomm's w8a16
build of the same model on the NPU.

## Caveats

* Accuracy numbers (3, 4) were run on an x86 CPU; they do not depend on the hardware. Latency and memory
  for the QCS6490 come from section 1 and, for the full app, from `bench/run_benchmark.py` on the board.
* FLORES/FLEURS are general-domain (news, Wikipedia). Factory speech has more numbers and part names.
