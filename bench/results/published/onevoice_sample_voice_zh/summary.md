### MindBridge benchmark (voice mode, 20261022-224030)

Device: x86_64, Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, 8028 MB RAM. Network default route during run: yes. Outbound connections blocked: 0.

| Stage | Model | Runs on | Size |
|---|---|---|---|
| Voice activity | Silero VAD v5 | CPU | 0.6 MB |
| Speech recognition | whisper-large-v3-turbo-int8 (CPU, CTranslate2) | CPU | 1547.3 MB |
| Translation | envit5-translation-ct2-int8 (CTranslate2 int8, CPU) | CPU | 265.7 MB |
| Translation | nllb-200-distilled-1.3B-ct2-int8 (CTranslate2 int8, CPU) | CPU | 1340.7 MB |
| Speech synthesis (Vietnamese) | vits-piper-vi_VN-vais1000-medium | CPU | 60.2 MB |
| Speech synthesis (English) | vits-piper-en_US-amy-low | CPU | 60.2 MB |
| Speech synthesis (Chinese) | vits-piper-zh_CN-huayan-medium | CPU | 60.3 MB |
| Operational memory | Rule engine + SQLite | CPU | 0.0 MB |
| **Total** | | | **3335.0 MB** |

Peak process RAM: **4650.0 MB**. Model load time: 12.04 s.

| Direction | N | BLEU | chrF++ | ASR WER/CER | ASR ms p50 | MT ms p50 | TTS ms p50 | Speech→translation ms p50 | Total ms p90 |
|---|---|---|---|---|---|---|---|---|---|
| vi-zh | 180 | 38.35 | 28.46 | 16.27% | 8718.7 | 1712.1 | 175.8 | 10475.7 | 11756.7 |
| zh-vi | 180 | 27.32 | 48.77 | 3.7% | 8983.7 | 1782.4 | 145.4 | 10839.9 | 12625.5 |
