#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python3}"
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi

"$PYTHON" -m pip install -r requirements-build.txt
"$PYTHON" -m PyInstaller --noconfirm --clean --windowed --name Setlist setlist.py

rm -f dist/Setlist-macos.dmg
hdiutil create -volname "Setlist" -srcfolder "dist/Setlist.app" -ov -format UDZO "dist/Setlist-macos.dmg"
echo "Skapade dist/Setlist-macos.dmg"
