### MindBridge benchmark (voice mode, 20261022-191246)

Device: x86_64, Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, 8028 MB RAM. Network default route during run: yes. Outbound connections blocked: 0.

| Stage | Model | Runs on | Size |
|---|---|---|---|
| Voice activity | Silero VAD v5 | CPU | 0.6 MB |
| Speech recognition | whisper-large-v3-turbo-int8 (CPU, CTranslate2) | CPU | 1547.3 MB |
| Translation | nllb-200-distilled-1.3B-ct2-int8 (CTranslate2 int8, CPU) | CPU | 1340.7 MB |
| Speech synthesis (Vietnamese) | vits-piper-vi_VN-vais1000-medium | CPU | 60.2 MB |
| Speech synthesis (English) | vits-piper-en_US-amy-low | CPU | 60.2 MB |
| Operational memory | Rule engine + SQLite | CPU | 0.0 MB |
| **Total** | | | **3009.0 MB** |

Peak process RAM: **4391.9 MB**. Model load time: 8.53 s.

| Direction | N | BLEU | chrF++ | ASR WER/CER | ASR ms p50 | MT ms p50 | TTS ms p50 | Speech→translation ms p50 | Total ms p90 |
|---|---|---|---|---|---|---|---|---|---|
| vi-en | 40 | 23.96 | 47.47 | 13.8% | 9249.0 | 3139.4 | 415.9 | 12733.7 | 14395.8 |
| en-vi | 40 | 34.29 | 53.94 | 4.98% | 8762.0 | 3193.1 | 467.0 | 12123.4 | 15524.2 |
| vi-ko | 40 | 23.49 | 19.88 | 13.8% | 8687.9 | 2595.7 | 1549.7 | 11364.9 | 14448.7 |
| ko-vi | 40 | 20.53 | 42.19 | 5.53% | 8623.6 | 3074.2 | 431.8 | 11901.3 | 14076.7 |
| vi-zh | 40 | 15.34 | 12.42 | 13.8% | 8623.9 | 2036.6 | 338.4 | 10873.7 | 12216.4 |
| zh-vi | 40 | 21.36 | 42.75 | 10.27% | 8731.6 | 3260.5 | 407.1 | 12076.2 | 14185.6 |
