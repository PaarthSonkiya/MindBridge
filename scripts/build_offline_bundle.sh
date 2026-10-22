#!/usr/bin/env bash
# Build the judges' OFFLINE installation bundle (run on any machine WITH internet).
#
# Produces dist/mindbridge-offline-<version>-aarch64.tar.gz containing:
#   app/        this repository at HEAD (code, UI, config, samples, docs, benchmark tool)
#   wheels/     every Python dependency for aarch64 / CPython 3.12, pinned by requirements-aarch64.lock
#   models/     the models the app uses + manifest.json with sizes, sha256 sums and licences
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
if [ -f "$ROOT/requirements-aarch64.lock" ]; then
  # Exact, tested versions (includes onnxruntime-qnn and every transitive dependency).
  pip download -r "$ROOT/requirements-aarch64.lock" --no-deps -d "$STAGE/wheels" "${PLATS[@]}" "${COMMON[@]}"
else
  pip download -r "$ROOT/requirements.txt" -d "$STAGE/wheels" "${PLATS[@]}" "${COMMON[@]}"
  # The requirements marker for onnxruntime-qnn is evaluated on THIS machine, so fetch it explicitly.
  pip download "onnxruntime-qnn>=2.7.0" -d "$STAGE/wheels" "${PLATS[@]}" "${COMMON[@]}"
fi
# pip itself, so the installer can bootstrap it where Ubuntu's python3-venv/ensurepip is missing.
pip download pip -d "$STAGE/wheels" --no-deps "${PLATS[@]}" "${COMMON[@]}"
# opencc-python-reimplemented is pure Python but only published as an sdist on some mirrors.
ls "$STAGE/wheels" | grep -qi opencc || pip wheel --no-deps -w "$STAGE/wheels" opencc-python-reimplemented
echo "$(ls "$STAGE/wheels" | wc -l) wheels"

echo "== Models (only what the app uses; see bench/model_sizes.py)"
[ -f "$ROOT/models/mt/envit5-translation-ct2-int8/model.bin" ] || python3 "$ROOT/scripts/fetch_models.py"
mkdir -p "$STAGE/models"
for rel in $(python3 "$ROOT/bench/model_sizes.py" --list-shipped); do
  mkdir -p "$STAGE/models/$(dirname "$rel")"
  cp -rL "$ROOT/models/$rel" "$STAGE/models/$rel"
done
python3 - "$ROOT" "$STAGE/models" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
import fetch_models as f
f.write_manifest(f.default_licenses(), root=Path(sys.argv[2]))
PY
du -sh "$STAGE/models"

cp "$ROOT/scripts/install_offline.sh" "$STAGE/"
cp "$ROOT/scripts/run.sh" "$STAGE/app/scripts/run.sh"
(cd "$ROOT/dist" && tar -czf "mindbridge-offline-$VER-aarch64.tar.gz" "$(basename "$STAGE")")
du -sh "$ROOT/dist/mindbridge-offline-$VER-aarch64.tar.gz"
sha256sum "$ROOT/dist/mindbridge-offline-$VER-aarch64.tar.gz" | tee "$ROOT/dist/mindbridge-offline-$VER-aarch64.tar.gz.sha256"
