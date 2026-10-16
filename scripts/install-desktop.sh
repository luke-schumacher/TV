#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" == "--help" ]]; then
  echo "Install TV desktop in its checkout. Run from any directory; no sudo or services."
  echo "Requires Python 3.9+ and mpv (brew install mpv; sudo apt install python3-venv mpv)."
  exit 0
fi
if [[ $# -gt 0 ]]; then echo "Unknown argument: $1" >&2; exit 2; fi
command -v mpv >/dev/null || { echo "Install mpv first: brew install mpv (macOS); sudo apt install mpv (Debian/Ubuntu)." >&2; exit 1; }
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -e "$ROOT[desktop]"
if [[ ! -e "$ROOT/config.yaml" ]]; then
  cp "$ROOT/config.desktop.example.yaml" "$ROOT/config.yaml"
fi
echo "Edit $ROOT/config.yaml and point media_root at your shows."
printf 'Check: %q --desktop --check\n' "$ROOT/.venv/bin/nostalgiabox"
printf 'Watch: %q --desktop\n' "$ROOT/.venv/bin/nostalgiabox"
