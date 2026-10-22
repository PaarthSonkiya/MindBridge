# Hardware: what to get and how to set up the RB3 Gen 2

## What you need

| Item | Needed? | Notes |
|---|---|---|
| **Qualcomm RB3 Gen 2 Core Kit** (QCS6490, 6 GB RAM, 128 GB UFS) | Yes | Sold by Thundercomm. The kit includes a 12 V power supply, a digital mic and mini speakers. The Vision Kit adds cameras and 4 mics; not needed. Do **not** buy the "Lite" (QCS5430). |
| HDMI monitor or HDMI touchscreen | Yes | The board has full-size HDMI. A 7–10" HDMI touchscreen (USB for touch) makes it feel like a device; any monitor works for the video. |
| USB keyboard + mouse | Yes (setup) | Also lets judges press `1` / `2` to talk. |
| USB headset or USB speakerphone | Strongly recommended | The onboard mic works, but a close mic gives much better recognition in a noisy room. A speakerphone (mic + speaker in one USB device) is simplest for a two-person demo. |
| USB presentation clicker | Optional | Its Page Up / Page Down buttons map to the two talk buttons: a cheap physical push-to-talk. |
| USB-C cable (data) | Yes | For flashing Ubuntu from a laptop. |
| 3D-printed enclosure | Optional | Counts towards the +0.5 hardware bonus. A simple badge-style front panel around the screen and buttons is enough. |

## Install Ubuntu 24.04 on the board

Canonical publishes a certified Ubuntu 24.04 image for the QCS6490 (desktop and server):
<https://ubuntu.com/download/qualcomm-iot>. Use the **desktop** image (it has a browser and audio stack).

1. On a Linux laptop, build Qualcomm's flashing tool `qdl`:
   `git clone https://github.com/linux-msm/qdl && cd qdl && make`
2. Download the Ubuntu desktop image and the matching boot-firmware archive from the page above, and unpack them into one folder.
3. Put the board in EDL mode: hold the **F_DL** button while connecting power and USB-C, then release. `lsusb` shows `05c6:9008`.
4. From the image folder: `sudo ./qdl prog_firehose_ddr.elf rawprogram*.xml patch*.xml`
5. Reboot, log in (`ubuntu` / `ubuntu`, you'll be asked to change it), connect Wi-Fi **for setup only**.

## Install MindBridge (online, once)

```bash
git clone https://github.com/PaarthSonkiya/MindBridge && cd MindBridge
git checkout phase3-prototype
bash scripts/setup_rb3.sh
```

This adds Qualcomm's Ubuntu PPA, installs PortAudio and the FastRPC/QNN user-space packages that exist
in that PPA, creates `.venv`, installs Python packages (including `onnxruntime-qnn`, which bundles the
Hexagon v68 HTP libraries), downloads the models, and runs `python -m mindbridge doctor`.

The translation model is converted from Hugging Face on a laptop (`python scripts/fetch_models.py --only mt`)
because the conversion needs PyTorch; copy `models/mt/` to the board.

## Check the NPU

```bash
python -m mindbridge doctor --run
```

Look for `"qnn": {"available": true, ...}` and `"asr": "whisper-small-w8a16 (QNN HTP)"`. If QNN is not
available the app still works with Whisper on the CPU. The usual causes are:

* `/dev/fastrpc-cdsp` missing or not readable → the setup script adds a udev rule; reboot once.
* DSP can't find `libQnnHtpV68Skel.so` → `scripts/run.sh` sets `ADSP_LIBRARY_PATH` to the
  `onnxruntime_qnn` package folder; run the app through that script.

## Before recording

* Wi-Fi off: `nmcli radio wifi off` (and unplug Ethernet). The UI chip turns green: "Offline: no network".
* `alsamixer` → raise mic capture level; test with `arecord -d 3 t.wav && aplay t.wav`.
* Set the pair on screen (VI ⇄ EN first).
