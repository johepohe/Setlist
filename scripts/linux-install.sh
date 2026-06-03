#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Setlist"
INSTALL_DIR="${HOME}/.local/opt/${APP_NAME}"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$DESKTOP_DIR"
cp "$(dirname "$0")/Setlist" "$INSTALL_DIR/Setlist"
chmod +x "$INSTALL_DIR/Setlist"
ln -sfn "$INSTALL_DIR/Setlist" "$BIN_DIR/setlist"

cat > "$DESKTOP_DIR/setlist.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Setlist
Comment=PDF-visare för setlists
Exec=$INSTALL_DIR/Setlist
Terminal=false
Categories=AudioVideo;Viewer;
EOF

echo "Installerade Setlist."
echo "Starta via programmenyn eller kör: setlist"
