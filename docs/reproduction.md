# Reproduction guide (offline)

Everything below runs with the network **off**. The only online step is downloading the bundle.

## Environment we measured on

| | |
|---|---|
| Board | Qualcomm RB3 Gen 2 Core Kit, QCS6490 (Kryo 670 CPU, Hexagon 770 NPU / HTP v68), 6 GB RAM |
| OS | Ubuntu 24.04 LTS (Canonical QCS6490 desktop image), Python 3.12 |
| NPU runtime | onnxruntime 1.31.0 with onnxruntime-qnn 2.7.0 (QAIRT 2.51, HTP backend); all versions in `requirements-aarch64.lock` |
| Models | see `models/manifest.json` (paths, sizes, sha256, licences) |

## Option A: offline bundle (recommended)

```bash
tar -xzf mindbridge-offline-0.4.0-aarch64.tar.gz
cd mindbridge-offline-0.4.0-aarch64
bash install_offline.sh            # pip --no-index from wheels/, checks every model's sha256
cd app
bash scripts/run.sh                # UI full-screen on HDMI
```

Requirements: aarch64 Linux with glibc ≥ 2.34 and Python 3.12 (Ubuntu 24.04), the RB3 Gen 2's 6 GB RAM,
about 8 GB free disk (3.7 GB of models). `python3-venv` is not needed: the installer bootstraps pip
from the bundle. Without `/dev/fastrpc-cdsp` (no Qualcomm NPU) the same bundle runs with Whisper on the CPU.

No microphone yet? `python -m mindbridge file samples/en_machine4_restriction.wav --src en --tgt vi`.

## Option B: Docker

```bash
docker load < mindbridge-0.4-arm64.tar.gz
docker run --rm -it --network host --device /dev/fastrpc-cdsp --device /dev/snd \
  -v /usr/lib/dsp:/usr/lib/dsp:ro -v /usr/lib/aarch64-linux-gnu/libcdsprpc.so:/usr/lib/aarch64-linux-gnu/libcdsprpc.so:ro \
  -v $PWD/models:/app/models:ro -v $PWD/data:/app/data mindbridge:0.4
# open http://127.0.0.1:8765
```

## Verify, then measure

```bash
python -m mindbridge doctor --run          # models present, NPU status, network state, one test translation
python -m mindbridge file samples/*.wav --src vi --tgt en            # recorded speech → translation, with timings
python -m mindbridge translate --file sentences.txt --src vi --tgt en --output out.txt   # one sentence per line
python bench/run_benchmark.py --data <dataset> --mode text --require-offline
python bench/run_benchmark.py --data <dataset> --mode voice --require-offline --limit 100
```

`--require-offline` refuses to start if the board has a default route. Each run writes
`bench/results/<timestamp>/run.log` with the network snapshot before and after, the list of models
with where they ran, and the count of blocked outbound connections (expected: 0).

## Using the UI without reading code

* **Tap to speak** (blue = supervisor, yellow = operator), or keys `1` / `2`, or a USB clicker's
  Page Up / Page Down. Recording stops by itself after a short silence; tap again to stop early.
* **Ask about the line**: ask MindBridge a question ("Can we restart Machine 4?").
* **Shift handover**: summary of everything still open, in both languages, read aloud on request.
* **Run details**: models, NPU/CPU placement, sizes, memory use, live network state.
* Top bar: switch VI ⇄ EN / KO / ZH.

## Numbers for the submission (on our own RB3 Gen 2)

Copy the organisers' sample folders (`Vie-Eng dataset/`, `Vie-Kor dataset/`) to the board, switch the
network off, then:

```bash
python bench/run_benchmark.py --data ~/onevoice-samples --mode voice --require-offline --unscored-audio \
    --out bench/results/published/rb3gen2_voice
python bench/model_sizes.py
du -sh ~/mindbridge-offline-0.4.0-aarch64          # installed size, for the "model size" row
python docs/submission/build_submission.py --template template.docx \
    --out "MindBridge_Prototype Submission_V3.docx" --board bench/results/published/rb3gen2_voice
```

The voice run gives per-stage latency (ASR on the NPU, translation, speech synthesis), the
speech→translation and total times per direction, peak RAM, and the network state before and after.
Commit the folder so the submission's evidence links resolve.
