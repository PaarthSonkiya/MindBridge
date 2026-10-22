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
# pip does not expand manylinux tags downwards, so list every tag the board (glibc 2.39) accepts.
PLATS=(--platform manylinux_2_39_aarch64 --platform manylinux_2_35_aarch64 --platform manylinux_2_34_aarch64
       --platform manylinux_2_28_aarch64 --platform manylinux_2_27_aarch64 --platform manylinux_2_17_aarch64
       --platform manylinux2014_aarch64 --platform linux_aarch64)
COMMON=(--python-version "$PY" --implementation cp --abi "cp$PY" --abi abi3 --abi none --only-binary=:all:)
pip download -r "$ROOT/requirements.txt" -d "$STAGE/wheels" "${PLATS[@]}" "${COMMON[@]}"
# The requirements marker for onnxruntime-qnn is evaluated on THIS machine, so fetch it explicitly.
pip download "onnxruntime-qnn>=2.7.0" -d "$STAGE/wheels" "${PLATS[@]}" "${COMMON[@]}"
# opencc-python-reimplemented is pure Python but only published as an sdist on some mirrors.
ls "$STAGE/wheels" | grep -qi opencc || pip wheel --no-deps -w "$STAGE/wheels" opencc-python-reimplemented
echo "$(ls "$STAGE/wheels" | wc -l) wheels"

echo "== Models"
[ -f "$ROOT/models/manifest.json" ] || python3 "$ROOT/scripts/fetch_models.py"
cp -rL "$ROOT/models" "$STAGE/models"

cp "$ROOT/scripts/install_offline.sh" "$STAGE/"
cp "$ROOT/scripts/run.sh" "$STAGE/app/scripts/run.sh"
(cd "$ROOT/dist" && tar -czf "mindbridge-offline-$VER-aarch64.tar.gz" "$(basename "$STAGE")")
du -sh "$ROOT/dist/mindbridge-offline-$VER-aarch64.tar.gz"
sha256sum "$ROOT/dist/mindbridge-offline-$VER-aarch64.tar.gz" | tee "$ROOT/dist/mindbridge-offline-$VER-aarch64.tar.gz.sha256"
