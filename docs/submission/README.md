# Prototype Submission document

The organisers' template (Phase 3 "Prototype Submission Template", Google Doc linked in the Phase 3
email) is filled automatically, so the document always matches the published evidence:

```bash
# download the template once: File → Download → Microsoft Word (.docx) → template.docx
python docs/submission/build_submission.py --template template.docx \
    --out "MindBridge_Prototype Submission_V3.docx"

# after the benchmark has been run on our own RB3 Gen 2 (bench/run_benchmark.py --mode voice ...):
python docs/submission/build_submission.py --template template.docx \
    --out "MindBridge_Prototype Submission_V3.docx" --board bench/results/<board-run-folder>
```

* Wording: `content.py`. Numbers: read from `bench/results/published/` (organisers' sample set, AI Hub
  profiles) and from `--board`.
* Anything that can only come from our own board or the demo video stays as a yellow
  **[TO FILL …]**; the script prints how many remain. Never replace one with an estimate.
* Submit as **`MindBridge_Prototype Submission_V3.docx`** (or export to PDF) through the submission form.
