#!/usr/bin/env bash
set -euo pipefail

rm -f "${HOME}/.local/bin/setlist"
rm -f "${HOME}/.local/share/applications/setlist.desktop"
rm -rf "${HOME}/.local/opt/Setlist"

echo "Avinstallerade Setlist. Sparade setlists ligger kvar i ~/.local/share/Setlist."
