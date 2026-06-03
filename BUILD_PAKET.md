# Bygga installationspaket

Programmet paketeras med PyInstaller. Bygg på respektive operativsystem för att få rätt format.

## Linux

```bash
source .venv/bin/activate
bash scripts/build_linux.sh
```

Resultat: `dist/Setlist-linux-x86_64.tar.gz`

Packa upp filen och kör `install.sh`. Programmet installeras till `~/.local/opt/Setlist`, kommandot `setlist` läggs i `~/.local/bin`, och en programmenyfil skapas.

## Windows

Kör i PowerShell på Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
.\scripts\build_windows.ps1
```

Resultat: `dist\Setlist-windows-x64.zip` med `Setlist.exe`.

## macOS

Kör på macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
bash scripts/build_macos.sh
```

Resultat: `dist/Setlist-macos.dmg` med `Setlist.app`.

## Sparade setlists

När programmet körs från källkod används `setlists.json` i projektmappen. När programmet körs som paketerad app sparas setlists per användare:

- Windows: `%APPDATA%\Setlist\setlists.json`
- macOS: `~/Library/Application Support/Setlist/setlists.json`
- Linux: `~/.local/share/Setlist/setlists.json`
