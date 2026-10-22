### MindBridge benchmark (voice mode, 20261022-234640)

Device: x86_64, Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, 8028 MB RAM. Network default route during run: yes. Outbound connections blocked: 0.

| Stage | Model | Runs on | Size |
|---|---|---|---|
| Voice activity | Silero VAD v5 | CPU | 0.6 MB |
| Speech recognition | whisper-large-v3-turbo-int8 (CPU, CTranslate2) | CPU | 1547.3 MB |
| Translation | envit5-translation-ct2-int8 (CTranslate2 int8, CPU) | CPU | 265.7 MB |
| Speech synthesis (Vietnamese) | vits-piper-vi_VN-vais1000-medium | CPU | 60.2 MB |
| Speech synthesis (English) | vits-piper-en_US-amy-low | CPU | 60.2 MB |
| Operational memory | Rule engine + SQLite | CPU | 0.0 MB |
| **Total** | | | **1934.0 MB** |

Peak process RAM: **2588.6 MB**. Model load time: 7.36 s.

| Direction | N | BLEU | chrF++ | ASR WER/CER | ASR ms p50 | MT ms p50 | TTS ms p50 | Speech→translation ms p50 | Total ms p90 |
|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 29.55 | 49.15 | 7.6% | 8843.6 | 317.9 | 141.2 | 9255.5 | 9910.9 |
| en-vi (no reference) | 100 | — | — | — | 8685.3 | 600.4 | 303.3 | 9354.2 | 10457.8 |

100 recordings in the dataset have no matching sentence text.
