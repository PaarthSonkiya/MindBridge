# MindBridge on a Mac (Phase 3 demo device)

Tested configuration: MacBook Air, Apple M5, 16 GB RAM, macOS. Any Apple Silicon Mac (M1 or later) with
8 GB free disk works the same way. Everything runs on the Mac's CPU, offline: Whisper large-v3-turbo
(int8), envit5 / NLLB-200 translation (int8) and Piper / Supertonic speech.

No admin password, Homebrew or Xcode is needed. Keep the Mac on its charger for long runs.

## 1. Install (online, once, about 20–40 minutes)

Open **Terminal** (Spotlight → "Terminal") and paste:

```bash
cd ~
curl -L -o mindbridge.zip https://github.com/PaarthSonkiya/MindBridge/archive/refs/heads/main.zip
unzip -q mindbridge.zip && cd MindBridge-main
bash scripts/setup_mac.sh
```

The script installs Python 3.12 for this user only, the exact package versions MindBridge was tested
with, and the models (about 3.5 GB), then runs a self-check that translates one sentence. It ends with
"Done. Next: …". Two macOS pop-ups may appear: "install command line developer tools?" → **Not Now**
(not needed), and "Terminal would like to access the microphone" → **OK**.

Or the same in one line, which also puts three double-click icons on the Desktop (Start MindBridge,
MindBridge Benchmark, Build MindBridge Package):

```bash
curl -fsSL https://raw.githubusercontent.com/PaarthSonkiya/MindBridge/main/scripts/install_mac.sh | bash
```

Later code updates: `cd ~/MindBridge-main && bash scripts/update_mac.sh` (keeps the models), or run the
one-line installer again.

## 2. First run

1. Turn **Wi-Fi off** (Control Center → Wi-Fi).
2. In Terminal: `cd ~/MindBridge-main && bash scripts/run.sh`
3. The UI opens full screen (Chrome if installed, otherwise Safari). The chips at the top should read
   **Offline: no network** and **Speech on CPU · Apple M5**.
4. Click **Tap to speak** (or press `1` for the Supervisor, `2` for the Operator), say a sentence, stop.
   The first time, macOS asks whether **Terminal** may use the microphone: click **Allow**. If you
   missed it: System Settings → Privacy & Security → Microphone → turn on Terminal, then restart run.sh.
5. Stop MindBridge with **Ctrl+C** in the Terminal window.

No microphone handy? `. .venv/bin/activate && python -m mindbridge file samples/vi_*.wav --src vi --tgt en`

## 3. Measure (offline, about 1 hour, unattended)

Put the organisers' sample folders (`Vie-Eng dataset`, `Vie-Kor dataset`, `Vie-Man dataset`) in
`~/onevoice-samples`, turn Wi-Fi off, plug in the charger, then:

```bash
cd ~/MindBridge-main && . .venv/bin/activate
caffeinate -i python bench/run_benchmark.py --data ~/onevoice-samples --mode text \
    --require-offline --out bench/results/published/mac_m5_text
caffeinate -i python bench/run_benchmark.py --data ~/onevoice-samples --mode voice \
    --require-offline --unscored-audio --out bench/results/published/mac_m5_voice
python bench/model_sizes.py
```

Or double-click **MindBridge Benchmark** on the Desktop (`bash scripts/benchmark_mac.sh`): it runs the
same three commands and leaves `mindbridge-mac-results.zip` on the Desktop. `caffeinate` keeps the Mac awake; `--require-offline` refuses to start while Wi-Fi is on. Each folder gets
`summary.md` (the table), `summary.json`, `results.jsonl` (every sentence) and `run.log` (device, models,
network state before and after). Zip `bench/results/published/mac_m5_text`, `mac_m5_voice` and
`model_sizes_mac.json` and send them to the team.

## 4. Record the demo video

See `docs/video_shot_list.md` (Mac section). In short: one uncut take, a phone on a tripod filming the
Mac and the speakers, plus a screen recording (Cmd+Shift+5 → Record Entire Screen → Options →
Microphone: MacBook Air Microphone). Show Wi-Fi being switched off first, then run the scenario.

## 5. Build the offline package for the judges

With Wi-Fi on (it downloads the wheels once):

```bash
cd ~/MindBridge-main && bash scripts/build_offline_bundle_mac.sh
```

It writes `dist/mindbridge-offline-0.4.0-macos-arm64.tar.gz` (about 3.5 GB) and its `.sha256`. Upload
both to Google Drive, sharing "anyone with the link".

Then test it the way a judge would: Wi-Fi off, unpack it in another folder, `bash install_offline_mac.sh`,
`cd app && bash scripts/run.sh`.

## Troubleshooting

| Problem | Fix |
|---|---|
| Nothing is recognised ("Didn't catch that") | Terminal has no microphone permission: System Settings → Privacy & Security → Microphone → Terminal on; restart run.sh |
| No sound from the translation | Check the Mac's output device and volume; `python -m mindbridge doctor` lists audio devices |
| "Network is on" chip stays amber | Turn off Wi-Fi and unplug any Ethernet/USB network adapter; a VPN also counts as a network |
| Port 8765 in use | A previous run is still going: press Ctrl+C in its Terminal window |
| Very slow first sentence | Normal: models load and warm up on the first turn |
| Anything else | `python -m mindbridge doctor --run` and `data/mindbridge.log`; send both to the team |
