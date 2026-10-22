### MindBridge benchmark (text mode, 20261022-215832)

Device: x86_64, Linux-6.18.44-fc-v140-x86_64-with-glibc2.39, 8028 MB RAM. Network default route during run: yes. Outbound connections blocked: 0.

| Stage | Model | Runs on | Size |
|---|---|---|---|
| Voice activity | Silero VAD v5 | CPU | 0.6 MB |
| Speech recognition | whisper-large-v3-turbo-int8 (CPU, CTranslate2) | CPU | 1547.3 MB |
| Translation | envit5-translation-ct2-int8 (CTranslate2 int8, CPU) | CPU | 265.7 MB |
| Translation | nllb-200-distilled-1.3B-ct2-int8 (CTranslate2 int8, CPU) | CPU | 1340.7 MB |
| Operational memory | Rule engine + SQLite | CPU | 0.0 MB |
| **Total** | | | **3154.3 MB** |

Peak process RAM: **4188.1 MB**. Model load time: 9.56 s.

| Direction | N | BLEU | chrF++ | MT ms mean | MT ms p90 |
|---|---|---|---|---|---|
| vi-en | 100 | 35.09 | 54.5 | 349.8 | 482.3 |
| vi-ko | 180 | 32.59 | 28.32 | 1248.5 | 1784.5 |
| ko-vi | 180 | 19.33 | 37.7 | 1399.8 | 1946.8 |
| vi-zh | 180 | 40.86 | 30.75 | 1876.0 | 2772.9 |
| zh-vi | 180 | 27.83 | 50.09 | 2023.1 | 2900.6 |

100 recordings in the dataset have no matching sentence text.
