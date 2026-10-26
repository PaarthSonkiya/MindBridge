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
* Values only a person can supply (video link and timestamps, package link, test conditions, microphone
  model): copy `manual_fields.example.json` to `manual_fields.json`, fill it, add `--manual manual_fields.json`.
  Re-running the script then never loses them.
* Submit as **`MindBridge_Prototype Submission_V3.docx`** (or export to PDF) through the submission form.

## The offline package (for the "Offline package" link)

Build it on any Linux machine with internet (the RB3 Gen 2 itself works, during its online setup):

```bash
git clone https://github.com/PaarthSonkiya/MindBridge && cd MindBridge
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
python scripts/fetch_models.py               # ~3.7 GB of models, once
bash scripts/build_offline_bundle.sh         # → dist/mindbridge-offline-0.4.0-aarch64.tar.gz (+ .sha256)
```

The package is about 3.5 GB. Upload the `.tar.gz` and its `.sha256` to Google Drive (or a GitHub release,
split below 2 GB per file), set sharing to "anyone with the link", and paste the link in section 3.1.
