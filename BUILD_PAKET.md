# Bygga installationspaket

Programmet paketeras med PyInstaller. Bygg på respektive operativsystem för att få rätt format.

## Linux

Linux-paket måste byggas på en distribution med samma eller äldre glibc än den
äldsta distribution som ska stödjas. Projektets GitHub Actions-bygge använder
därför Ubuntu 22.04 (glibc 2.35). Det färdiga paketet fungerar på Debian 12 och
MX Linux 23 (glibc 2.36) samt nyare x86_64-distributioner.

Rekommenderat: öppna **Actions > Build installers > Run workflow** på GitHub och
ladda ner artefakten `Setlist-linux-x86_64` när bygget är klart.

För ett lokalt bygge på en kompatibel, äldre Linux-distribution:

```bash
source .venv/bin/activate
bash scripts/build_linux.sh
```

Resultat: `dist/Setlist-linux-x86_64.tar.gz`

Bygg inte distributionspaketet på Debian 13, Ubuntu 24.04 eller någon annan
nyare byggmaskin om det ska köras på Debian 12. PyInstaller kan paketera Python
och programmets bibliotek, men inte göra glibc bakåtkompatibelt.

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

## Publicera nedladdningar på GitHub

Knapparna i `beskrivning.html` pekar på senaste GitHub Release:

- `https://github.com/johepohe/Setlist/releases/latest/download/Setlist-windows-x64.zip`
- `https://github.com/johepohe/Setlist/releases/latest/download/Setlist-macos.dmg`
- `https://github.com/johepohe/Setlist/releases/latest/download/Setlist-linux-x86_64.tar.gz`

Skapa en release på GitHub och ladda upp filerna som release assets med exakt dessa filnamn. När du gör en ny version skapar du en ny release med nya filer, så fortsätter länkarna att peka rätt via `/releases/latest/`.
