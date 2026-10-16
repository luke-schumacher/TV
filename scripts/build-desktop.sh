#!/usr/bin/env bash
# Builds an unsigned, platform-native app directory. mpv remains a system dependency.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python -m PyInstaller --noconfirm --clean --windowed --name TV \
  --collect-submodules nostalgiabox --collect-data nostalgiabox \
  --hidden-import yaml scripts/desktop-entry.py
if [[ "$(uname -s)" == Darwin ]]; then
  ditto -c -k --sequesterRsrc --keepParent dist/TV.app dist/TV-macOS-unsigned.zip
else
  tar -czf dist/TV-linux-unsigned.tar.gz -C dist TV
fi
