# Build the free single-project desktop app (.exe) — one self-contained folder that runs the
# whole platform locally: FastAPI + the web SPA on 127.0.0.1:8765, SQLite, single-operator local
# mode (no Docker / Postgres / MinIO / login). Output: services/api/dist_desktop/AEC-BIM/AEC-BIM.exe
#
# Usage (from services/api):  ./build-desktop.ps1
# Prereqs: the api .venv, Node (for the web build). PyInstaller is auto-installed if missing.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Resolve-Path (Join-Path $here "..\..")
$py   = Join-Path $here ".venv\Scripts\python.exe"

Write-Host "==> Building the desktop-mode web SPA (same-origin API base)..." -ForegroundColor Cyan
Push-Location (Join-Path $repo "apps\web")
npm run build:desktop
Pop-Location

Write-Host "==> Ensuring PyInstaller is installed..." -ForegroundColor Cyan
& $py -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) { & $py -m pip install pyinstaller }

Write-Host "==> Packaging the .exe (FastAPI + SPA + 68 module defs + ifcopenshell)..." -ForegroundColor Cyan
Push-Location $here
& $py -m PyInstaller desktop.spec --noconfirm --distpath dist_desktop --workpath build_desktop
Pop-Location

$exe = Join-Path $here "dist_desktop\AEC-BIM\AEC-BIM.exe"
if (Test-Path $exe) {
    Write-Host "`nDone. Run it:  $exe" -ForegroundColor Green
    Write-Host "It opens http://127.0.0.1:8765/ and stores data under %LOCALAPPDATA%\AEC-BIM." -ForegroundColor Green
} else {
    Write-Error "Build finished but the .exe is missing — check the PyInstaller output above."
}
