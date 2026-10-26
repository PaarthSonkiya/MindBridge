#!/usr/bin/env bash
# Put double-click launchers for MindBridge on the Mac's Desktop (they open in Terminal).
#   bash scripts/mac_launchers.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DESK="$HOME/Desktop"
mkdir -p "$DESK"

make_launcher() {  # make_launcher "<icon name>" "<command>"
  local f="$DESK/$1.command"
  cat > "$f" <<EOF
#!/bin/bash
cd "$ROOT" || exit 1
$2
echo
read -r -p "Finished. Press Return to close this window. " _
EOF
  chmod +x "$f"
}

make_launcher "Start MindBridge" "bash scripts/run.sh"
make_launcher "MindBridge Benchmark" "bash scripts/benchmark_mac.sh"
make_launcher "Build MindBridge Package" "bash scripts/build_offline_bundle_mac.sh"
echo "Added to the Desktop: Start MindBridge, MindBridge Benchmark, Build MindBridge Package."
