#!/usr/bin/env bash
# One-line MindBridge installer for an Apple Silicon Mac. Paste into Terminal (Wi-Fi on):
#
#   curl -fsSL https://raw.githubusercontent.com/PaarthSonkiya/MindBridge/main/scripts/install_mac.sh | bash
#
# Puts MindBridge in ~/MindBridge-main, installs Python, packages and models (about 3.5 GB, 20–40 minutes),
# and adds three icons to the Desktop: Start MindBridge, MindBridge Benchmark, Build MindBridge Package.
# Running it again updates the code, or finishes an install that stopped part-way; downloaded models are kept.
set -euo pipefail

# Everything is inside main() so bash reads the whole script before running it (safe with curl | bash).
main() {
  local dest="$HOME/MindBridge-main"
  local zip_url="https://github.com/PaarthSonkiya/MindBridge/archive/refs/heads/main.zip"

  if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
    echo "This installer is for Apple Silicon Macs (M1 or later)."; exit 1
  fi

  if [ -x "$dest/.venv/bin/python" ]; then
    echo "MindBridge is already installed in $dest: updating it."
    bash "$dest/scripts/update_mac.sh" < /dev/null
  else
    echo "Downloading MindBridge…"
    local tmp
    tmp="$(mktemp -d)"
    curl -fsSL -o "$tmp/mindbridge.zip" "$zip_url"
    unzip -q "$tmp/mindbridge.zip" -d "$tmp"
    mkdir -p "$dest"
    # Copy over any earlier attempt instead of deleting it, so models already downloaded are kept.
    (cd "$tmp"/MindBridge-*/ && tar -cf - .) | (cd "$dest" && tar -xf -)
    rm -rf "$tmp"
    bash "$dest/scripts/setup_mac.sh" < /dev/null
  fi
  bash "$dest/scripts/mac_launchers.sh"
}

main "$@"
