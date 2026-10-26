#!/usr/bin/env bash
# Build the judges' OFFLINE package for Apple Silicon Macs. Run it on the Mac after scripts/setup_mac.sh
# (it reuses the models and the Python that setup installed), with internet for the wheel download.
#
# Produces dist/mindbridge-offline-<version>-macos-arm64.tar.gz containing:
#   python/     a standalone CPython 3.12 for Apple Silicon (the one setup_mac.sh installed via uv)
#   wheels/     every Python dependency, pinned by requirements-macos-arm64.lock
#   models/     the models the Mac configuration uses + manifest.json (sizes, sha256, licences)
#   app/        this repository at HEAD (code, UI, config, samples, docs, benchmark tool)
#   install_offline_mac.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -d .venv ] && . .venv/bin/activate
VER="$(python -c 'import mindbridge; print(mindbridge.__version__)')"
NAME="mindbridge-offline-$VER-macos-arm64"
STAGE="$ROOT/dist/$NAME"
rm -rf "$STAGE" && mkdir -p "$STAGE/wheels" "$STAGE/models"

echo "== Code"
mkdir -p "$STAGE/app"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git archive --format=tar HEAD | tar -x -C "$STAGE/app"
else  # downloaded as a ZIP from GitHub: copy the tree without local environments, models and run outputs
  tar -c --exclude ./.venv --exclude ./models --exclude ./data --exclude ./dist --exclude "*/__pycache__" \
      --exclude "./bench/results/[0-9]*" -f - . | tar -x -C "$STAGE/app"
fi

echo "== Python 3.12 (standalone build)"
PYHOME="$(python -c 'import sys; print(sys.base_prefix)')"
case "$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])')" in
  3.12) ;;
  *) echo "Run scripts/setup_mac.sh first (needs its Python 3.12 environment)"; exit 1 ;;
esac
cp -R "$PYHOME" "$STAGE/python"
# A standalone build is relocatable; drop caches and the test suite to save space.
find "$STAGE/python" -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -rf "$STAGE/python/lib/python3.12/test"

echo "== Wheels for macOS arm64, CPython 3.12"
python -m pip download -q -r requirements-macos-arm64.lock --no-deps --only-binary=:all: -d "$STAGE/wheels"
python -m pip download -q pip --no-deps -d "$STAGE/wheels"
echo "$(ls "$STAGE/wheels" | wc -l | tr -d ' ') wheels"

echo "== Models"
for rel in $(python bench/model_sizes.py --config config/mac.toml --list-shipped); do
  mkdir -p "$STAGE/models/$(dirname "$rel")"
  cp -RL "models/$rel" "$STAGE/models/$rel"
done
python - "$ROOT" "$STAGE/models" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
import fetch_models as f
f.write_manifest(f.default_licenses(), root=Path(sys.argv[2]))
PY
du -sh "$STAGE/models"

cp scripts/install_offline_mac.sh "$STAGE/"
(cd "$ROOT/dist" && COPYFILE_DISABLE=1 tar -czf "$NAME.tar.gz" "$NAME" && shasum -a 256 "$NAME.tar.gz" | tee "$NAME.tar.gz.sha256")
du -sh "$ROOT/dist/$NAME.tar.gz"
echo "Upload dist/$NAME.tar.gz and its .sha256 (Google Drive, 'anyone with the link')."
