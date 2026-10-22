# From here to submission (deadline: Fri 13 Nov 2026, 23:59 Vietnam time = 00:59 Sat 14 Nov Singapore)

Everything that can be done without the board is done: code, models, benchmarks on the organisers'
samples, the filled template (with yellow **[TO FILL]** marks), the install package script. What is left
needs the real RB3 Gen 2, a camera and a submission form.

| # | When | What | How | Done when |
|---|---|---|---|---|
| 1 | Now | Order the hardware | `docs/hardware.md`: RB3 Gen 2 **Core** Kit (not Lite), HDMI screen, USB keyboard, USB speakerphone or headset | Order confirmed; check the delivery date leaves ≥ 5 days before 13 Nov |
| 2 | Fri 23 Oct | Workshop (18:00–19:00 SGT) | Ask the questions in `docs/workshop_questions.md`, especially the missing EN→VI references and the onnxruntime version for QNN | Answers noted in the same file |
| 3 | Board arrives | Flash Ubuntu 24.04 and install | `docs/hardware.md` → `bash scripts/setup_rb3.sh` (online, once) | `python -m mindbridge doctor --run` shows `"qnn": {"available": true}` |
| 4 | Same day | Measure on the board | Copy the sample set to the board, network off, then the commands in `docs/reproduction.md` → "Numbers for the submission" | `bench/results/published/rb3gen2_voice/summary.md` exists; commit and push it |
| 5 | Same day | Build the offline package | `bash scripts/build_offline_bundle.sh` (on the board or a Linux laptop); upload the `.tar.gz` + `.sha256` to Google Drive, "anyone with the link" | Link opens in a private browser window |
| 6 | Rehearse twice | Record the demo video | `docs/demo_scenario.md` + `docs/video_shot_list.md`; one uncut take, network switched off on camera | Video uploaded (YouTube unlisted or Drive), timestamps noted |
| 7 | After 4–6 | Finish the document | `python docs/submission/build_submission.py --template template.docx --out "MindBridge_Prototype Submission_V3.docx" --board bench/results/published/rb3gen2_voice`, then replace the remaining yellow marks (video link and timestamps, test conditions, microphone model, package link) by hand | No yellow left; export a PDF too |
| 8 | ≥ 1 day early | Submit | Form: https://forms.gle/Qhdni9hdFm19ZJfF6; file name `MindBridge_Prototype Submission_V3.docx` (or .pdf); "changes since Phase 2": paste `docs/changes_since_phase2.md` | Confirmation email received |

Running on real hardware is mandatory. If delivery looks late, raise it at the workshop or by replying to the
organisers' email early (they have devices at the SAIH space in Ho Chi Minh City). Where a number truly
cannot be measured, the template asks for "Not measured" plus the reason. Never put an estimate there.
