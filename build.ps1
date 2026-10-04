# Build de Navix Tools: dos ejecutables con PyInstaller y el instalador con Inno Setup.
#   powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = ".\.venv\Scripts\python.exe"

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Los tests fallan: no se genera el build." }

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

# NavixTools.exe: la barra (sin consola), más el helper elevado y el guardado de perfiles.
& $python -m PyInstaller --noconfirm --onedir --windowed --name NavixTools `
    --icon branding\navix.ico `
    --add-data "dock\assets;dock\assets" `
    --hidden-import dock.tools.ip_switch --hidden-import dock.tools.ai_usage `
    --hidden-import dock.__main__ --hidden-import ipswitch.__main__ `
    dock_run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (NavixTools) falló." }

# cli\ipswitch.exe: CLI de consola y registrador de la status line (sin Qt, liviano).
& $python -m PyInstaller --noconfirm --onedir --console --name ipswitch `
    --hidden-import ipswitch.__main__ --hidden-import dock.statusline `
    --exclude-module PySide6 --exclude-module shiboken6 `
    ipswitch_cli.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (ipswitch) falló." }

Move-Item dist\ipswitch dist\NavixTools\cli

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "No se encontró Inno Setup 6 (ISCC.exe)." }
& $iscc installer\navix.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falló." }
Get-Item dist\Navix-Tools-Setup-*.exe
