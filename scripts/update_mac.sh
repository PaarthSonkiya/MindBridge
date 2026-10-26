#!/usr/bin/env bash
# Update the code of a ZIP-installed MindBridge on a Mac to the latest version on GitHub (needs internet).
# Keeps the Python environment (.venv), the models and the memory database; re-installs pinned packages.
#   bash scripts/update_mac.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL -o "$TMP/mb.zip" https://github.com/PaarthSonkiya/MindBridge/archive/refs/heads/main.zip
unzip -q "$TMP/mb.zip" -d "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -type d -name 'MindBridge-*' | head -1)"
# Copy everything except local state; bench/results keeps your own run folders.
(cd "$SRC" && tar -c --exclude ./.venv --exclude ./models --exclude ./data --exclude ./dist -f - .) | (cd "$ROOT" && tar -x -f -)
cd "$ROOT"
export PATH="$HOME/.local/bin:$PATH"
. .venv/bin/activate
uv pip install -q -r requirements-macos-arm64.lock
python scripts/fetch_models.py --target mac   # downloads only models that are new
echo "Updated to $(python -c 'import mindbridge; print(mindbridge.__version__)')."
