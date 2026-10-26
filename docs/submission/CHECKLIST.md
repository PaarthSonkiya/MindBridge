# From here to submission (deadline: Fri 13 Nov 2026, 23:59 Vietnam time = 00:59 Sat 14 Nov Singapore)

Phase 3 demo device: a MacBook Air (Apple M5, 16 GB). The Brief allows "other hardware prepared by the
team"; nothing is simulated. The RB3 Gen 2 build stays ready for the on-site rounds. Mac guide: `docs/mac.md`.

| # | What | How | Done when |
|---|---|---|---|
| 1 | Email the organisers | The two drafted emails (demo device; dataset questions), as replies to their Phase 3 email | Sent; note their answers in `docs/workshop_questions.md` |
| 2 | Install on the Mac (online, ~30 min) | `docs/mac.md` §1: download the ZIP, `bash scripts/setup_mac.sh` | It ends with "Done. Next:" and the self-check translated a sentence |
| 3 | First run | Wi-Fi off, `bash scripts/run.sh`, allow Terminal to use the microphone, say a sentence on each side | Chips read "Offline: no network" and "Speech on CPU · Apple M5"; translation is spoken |
| 4 | Benchmark (offline, ~1 h) | `docs/mac.md` §3 with the organisers' samples in `~/onevoice-samples` | `bench/results/published/mac_m5_text/` and `mac_m5_voice/` exist; zip them with `model_sizes_mac.json` and send them |
| 5 | Rehearse | `docs/demo_scenario.md` with the Vietnamese speaker (and a Korean speaker for Part B, optional) | One full run without restarts |
| 6 | Record the video | `docs/video_shot_list.md` (Mac section): phone on tripod + screen recording, Wi-Fi off on camera, one uncut take | Uploaded (YouTube unlisted or Drive, "anyone with the link"); timestamps noted |
| 7 | Build and test the offline package | `bash scripts/build_offline_bundle_mac.sh` (Wi-Fi on), then Wi-Fi off and install it in another folder as a judge would | `.tar.gz` + `.sha256` uploaded to Drive, link opens in a private window |
| 8 | Finish the document | Results from step 4 committed; `manual_fields.json` with video link, timestamps, package link, test conditions; `python docs/submission/build_submission.py --template template.docx --out "MindBridge_Prototype Submission_V3.docx" --manual manual_fields.json` | No yellow left; export a PDF too |
| 9 | Submit (≥ 1 day early) | Form: https://forms.gle/Qhdni9hdFm19ZJfF6; file `MindBridge_Prototype Submission_V3.docx` (or .pdf); "changes since Phase 2": paste `docs/changes_since_phase2.md` | Confirmation email received |

Never put an estimate where the template asks for a measured number; write "Not measured" and the reason.
