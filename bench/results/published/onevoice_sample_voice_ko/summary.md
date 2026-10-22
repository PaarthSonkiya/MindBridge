### MindBridge benchmark (voice mode, 20261023-001847)

Device: x86_64, Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, 8028 MB RAM. Network default route during run: yes. Outbound connections blocked: 0.

| Stage | Model | Runs on | Size |
|---|---|---|---|
| Voice activity | Silero VAD v5 | CPU | 0.6 MB |
| Speech recognition | whisper-large-v3-turbo-int8 (CPU, CTranslate2) | CPU | 1547.3 MB |
| Translation | envit5-translation-ct2-int8 (CTranslate2 int8, CPU) | CPU | 265.7 MB |
| Translation | nllb-200-distilled-1.3B-ct2-int8 (CTranslate2 int8, CPU) | CPU | 1340.7 MB |
| Speech synthesis (Vietnamese) | vits-piper-vi_VN-vais1000-medium | CPU | 60.2 MB |
| Speech synthesis (English) | vits-piper-en_US-amy-low | CPU | 60.2 MB |
| Speech synthesis (Korean) | sherpa-onnx-supertonic-3-tts-int8-2026-05-11 | CPU | 137.8 MB |
| Operational memory | Rule engine + SQLite | CPU | 0.0 MB |
| **Total** | | | **3412.5 MB** |

Peak process RAM: **4608.2 MB**. Model load time: 11.35 s.

| Direction | N | BLEU | chrF++ | ASR WER/CER | ASR ms p50 | MT ms p50 | TTS ms p50 | Speech→translation ms p50 | Total ms p90 |
|---|---|---|---|---|---|---|---|---|---|
| vi-ko | 180 | 30.67 | 27.04 | 4.6% | 8429.2 | 1200.2 | 619.9 | 9658.5 | 11145.9 |
| ko-vi | 180 | 18.24 | 36.91 | 7.22% | 8367.8 | 1229.4 | 90.4 | 9585.4 | 10483.8 |
