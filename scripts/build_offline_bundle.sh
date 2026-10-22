#!/usr/bin/env bash
# Build the judges' OFFLINE installation bundle (run on any machine WITH internet).
#
# Produces dist/mindbridge-offline-<version>-aarch64.tar.gz containing:
#   app/        this repository (code, UI, config)
#   wheels/     every Python dependency for aarch64 / CPython 3.12 (pip --no-index installs these)
#   models/     all models + manifest.json with sha256 sums
#   install_offline.sh, run.sh
#
# Upload the tarball to the GitHub release / Google Drive and put the link in the submission form.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="$(python3 -c 'import sys; sys.path.insert(0, "'"$ROOT"'"); import mindbridge; print(mindbridge.__version__)')"
PY="${PY_VERSION:-312}"
STAGE="$ROOT/dist/mindbridge-offline-$VER-aarch64"
rm -rf "$STAGE" && mkdir -p "$STAGE/wheels"

echo "== Code"
git -C "$ROOT" archive --format=tar HEAD | (mkdir -p "$STAGE/app" && tar -x -C "$STAGE/app")

echo "== Wheels for linux aarch64, CPython $PY"
for plat in manylinux_2_39_aarch64 manylinux_2_34_aarch64 manylinux_2_28_aarch64 manylinux2014_aarch64; do
  pip download -r "$ROOT/requirements.txt" -d "$STAGE/wheels" \
    --platform "$plat" --python-version "$PY" --implementation cp --only-binary=:all: && break || true
done
# pure-python packages without wheels for every tag
pip download -d "$STAGE/wheels" --no-deps --only-binary=:all: opencc-python-reimplemented || \
  pip download -d "$STAGE/wheels" --no-deps opencc-python-reimplemented

echo "== Models"
[ -f "$ROOT/models/manifest.json" ] || python3 "$ROOT/scripts/fetch_models.py"
cp -rL "$ROOT/models" "$STAGE/models"

cp "$ROOT/scripts/install_offline.sh" "$STAGE/"
cp "$ROOT/scripts/run.sh" "$STAGE/app/scripts/run.sh"
(cd "$ROOT/dist" && tar -czf "mindbridge-offline-$VER-aarch64.tar.gz" "$(basename "$STAGE")")
du -sh "$ROOT/dist/mindbridge-offline-$VER-aarch64.tar.gz"
sha256sum "$ROOT/dist/mindbridge-offline-$VER-aarch64.tar.gz" | tee "$ROOT/dist/mindbridge-offline-$VER-aarch64.tar.gz.sha256"
