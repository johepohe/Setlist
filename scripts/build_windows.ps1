$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir

$Python = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $Python = ".venv\Scripts\python.exe"
}

& $Python -m pip install -r requirements-build.txt
& $Python -m PyInstaller --noconfirm --clean --windowed --onefile --name Setlist setlist.py

$PackageDir = "dist\Setlist-windows"
Remove-Item -Recurse -Force $PackageDir -ErrorAction SilentlyContinue
Remove-Item -Force "dist\Setlist-windows-x64.zip" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $PackageDir | Out-Null
Copy-Item "dist\Setlist.exe" "$PackageDir\Setlist.exe"
Compress-Archive -Path "$PackageDir\*" -DestinationPath "dist\Setlist-windows-x64.zip"

Write-Host "Skapade dist\Setlist-windows-x64.zip"
