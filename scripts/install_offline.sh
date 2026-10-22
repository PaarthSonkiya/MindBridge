#!/usr/bin/env bash
# Install MindBridge on an RB3 Gen 2 (Ubuntu 24.04, aarch64) with NO network connection.
#
#   tar -xzf mindbridge-offline-*-aarch64.tar.gz && cd mindbridge-offline-*-aarch64
#   bash install_offline.sh
#   cd app && bash scripts/run.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/app"

command -v python3 >/dev/null || { echo "python3 is required (preinstalled on Ubuntu 24.04)"; exit 1; }
python3 -c 'import venv' 2>/dev/null || { echo "python3-venv is missing: sudo apt install python3-venv (needs network once)"; exit 1; }

python3 -m venv "$APP/.venv"
. "$APP/.venv/bin/activate"
pip install --no-index --find-links "$HERE/wheels" -r "$APP/requirements.txt"

rm -rf "$APP/models"
ln -s "$HERE/models" "$APP/models"

# Verify model integrity against the manifest.
python3 - "$HERE/models" <<'EOF'
import hashlib, json, sys, pathlib
root = pathlib.Path(sys.argv[1]); m = json.loads((root / "manifest.json").read_text())
bad = []
for f in m["files"]:
    p = root / f["path"]
    h = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    if h != f["sha256"]:
        bad.append(f["path"])
print(f"models: {len(m['files'])} files, {m['total_mb']} MB, {'all checksums OK' if not bad else 'MISMATCH: ' + ', '.join(bad)}")
sys.exit(1 if bad else 0)
EOF

if ! python3 -c 'import sounddevice' 2>/dev/null; then
  echo "Note: PortAudio (libportaudio2) not found — the UI will use the browser microphone instead."
fi
cd "$APP" && python -m mindbridge doctor || true
echo
echo "Installed. Start with:  cd $APP && bash scripts/run.sh"
