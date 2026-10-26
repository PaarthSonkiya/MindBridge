#!/usr/bin/env bash
# Install MindBridge on an Apple Silicon Mac (macOS 14+) with NO network connection and no admin rights.
#
#   shasum -a 256 -c mindbridge-offline-*-macos-arm64.tar.gz.sha256
#   tar -xzf mindbridge-offline-*-macos-arm64.tar.gz && cd mindbridge-offline-*-macos-arm64
#   bash install_offline_mac.sh
#   cd app && bash scripts/run.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/app"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "This package is for Apple Silicon Macs. For the Qualcomm RB3 Gen 2 use the aarch64 package."
  exit 1
fi

# Files from a browser download carry macOS's quarantine flag, which blocks the bundled Python and
# libraries from loading. They are ours to run, so clear it (no admin needed for your own files).
xattr -dr com.apple.quarantine "$HERE" 2>/dev/null || true

"$HERE/python/bin/python3" -m venv "$APP/.venv"
. "$APP/.venv/bin/activate"
python -m pip install --no-index --find-links "$HERE/wheels" -q --upgrade pip
python -m pip install --no-index --find-links "$HERE/wheels" -r "$APP/requirements-macos-arm64.lock"

rm -rf "$APP/models"
ln -s "$HERE/models" "$APP/models"

# Verify model integrity against the manifest.
python - "$HERE/models" <<'EOF'
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

cd "$APP" && python -m mindbridge doctor || true
echo
echo "Installed. Start with:  cd $APP && bash scripts/run.sh"
echo "The first time you speak, allow Terminal to use the microphone (System Settings → Privacy & Security → Microphone)."
