#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python3}"
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi

"$PYTHON" -m pip install -r requirements-build.txt
"$PYTHON" -m PyInstaller --noconfirm --clean --windowed --onefile --name Setlist setlist.py

PACKAGE_DIR="dist/Setlist-linux"
rm -rf "$PACKAGE_DIR" "dist/Setlist-linux-x86_64.tar.gz"
mkdir -p "$PACKAGE_DIR"
cp dist/Setlist "$PACKAGE_DIR/Setlist"
cp scripts/linux-install.sh "$PACKAGE_DIR/install.sh"
cp scripts/linux-uninstall.sh "$PACKAGE_DIR/uninstall.sh"
chmod +x "$PACKAGE_DIR/Setlist" "$PACKAGE_DIR/install.sh" "$PACKAGE_DIR/uninstall.sh"

tar -C dist -czf dist/Setlist-linux-x86_64.tar.gz Setlist-linux
echo "Skapade dist/Setlist-linux-x86_64.tar.gz"
