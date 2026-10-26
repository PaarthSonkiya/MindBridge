# Demo video: shot list (mandatory item 7.1)

Rules from the brief: one end-to-end run of the prepared scenario, from voice input to translated
output; the network must be visibly switched off **on the device** right before the run; no editing
or simulation; processing time visible on screen.

**Camera:** a phone on a tripod filming the monitor *and* the RB3 Gen 2 board and the speakers' hands,
in one continuous take. Optionally also screen-record the monitor for a sharper copy, but the phone take
is the one that proves it's the real device. Record room audio (the judges need to hear both voices and
the device speaking).

## Phase 3 recording on the MacBook (the demo device)

**Camera:** a phone on a tripod, landscape, filming the Mac's screen and keyboard *and* both speakers, in
one continuous take; this is the proof that it is a real device. At the same time record the screen on the
Mac (Cmd+Shift+5 → Record Entire Screen → Options → Microphone: MacBook Air Microphone) for a sharp copy.
Charger plugged in. Turn off notifications (Control Center → Focus → Do Not Disturb).

| Shot | Duration | What to show | Say on camera |
|---|---|---|---|
| 1 | 0:20 | The team, the MacBook (About This Mac: Apple M5, 16 GB) | "MindBridge running entirely on this MacBook Air, offline." |
| 2 | 0:40 | Control Center → **Wi-Fi off**. Terminal: `networksetup -getairportpower en0` → *Off*; `route -n get default` → *not in table*; `ping -c 1 8.8.8.8` → *No route to host* | "The laptop is now offline." |
| 3 | 0:40 | `cd ~/MindBridge-main && bash scripts/run.sh` → *Ready…*; UI opens; chips read **Offline: no network** and **Speech on CPU · Apple M5** | |
| 4 | 0:30 | **Run details**: models, sizes, memory, network state, *0 attempts blocked*. Close it. | "Speech recognition, translation and speech all run on this laptop." |
| 5 | ~24:00 | Scenario Part A (`docs/demo_scenario.md`), continuous; leave each turn's timing line visible for a moment | Only the scenario lines |
| 6 | ~6:00 | Switch to **Tiếng Việt ⇄ 한국어**, Part B (skip if you have no Korean speaker) | |
| 7 | 0:40 | **Shift handover**, read aloud; **Run details** again (peak memory, still 0 blocked) | |
| 8 | 0:20 | Terminal: `route -n get default` still *not in table* | "The whole session ran offline." |

Write down the timestamps (network off, first exchange, conflict alert, answer from memory, handover) for
the submission form.

## Recording on the RB3 Gen 2 (field-testing round)

| Shot | Duration | What to show | Say on camera |
|---|---|---|---|
| 1 | 0:20 | Team, the RB3 Gen 2 board up close (QCS6490 marking), USB mic/speaker, screen | "MindBridge on a Qualcomm RB3 Gen 2, QCS6490." |
| 2 | 0:40 | Terminal on the device: `nmcli radio wifi off`, unplug Ethernet, then `nmcli radio` (disabled), `ip route` (empty), `ping -c1 8.8.8.8` → *Network is unreachable* | "The device is now offline." |
| 3 | 0:40 | `bash scripts/run.sh` → terminal prints *Ready… ASR: whisper-large-v3-turbo-w8a16 (QNN HTP)*; UI opens; top bar shows **Offline: no network** and **Speech on NPU** | |
| 4 | 0:30 | Open **Run details**: model table (NPU/CPU, sizes), memory, network state, *0 attempts blocked*. Close it. | "Speech recognition runs on the Hexagon NPU; translation and speech on the CPU." |
| 5 | ~24:00 | Scenario Part A, continuous. Keep each turn's latency line visible for a moment. | Only the scenario lines |
| 6 | ~6:00 | Switch to VI ⇄ KO, Part B | |
| 7 | 0:40 | **Shift handover** dialog, read aloud; **Run details** again (peak memory, still 0 blocked) | |
| 8 | 0:20 | Terminal: `ip route` still empty | "Whole session offline." |

**Before you press record**

- [ ] Fresh memory: tap **Clear**
- [ ] `python -m mindbridge doctor --run` shows QNN available
- [ ] Mic level checked (`arecord -d 3 t.wav && aplay t.wav`)
- [ ] Fans on in the room to match the test venue's light background noise
- [ ] Phone storage for ~35 min of 1080p video, phone on charger
- [ ] Script printed for both speakers

**After recording:** upload unedited to Google Drive or YouTube (unlisted) and put the link in the form.
