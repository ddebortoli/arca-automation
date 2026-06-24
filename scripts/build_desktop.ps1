# Build the Facturador AFIP desktop app on Windows.
#
# Output: dist\Facturador\Facturador.exe
#
# Requirements:
#   - uv
#   - OpenSSL on PATH (AFIP signing uses the `openssl` CLI)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> Syncing dependencies (including PyInstaller)"
uv sync --group dev

Write-Host "==> Building desktop executable"
uv run pyinstaller packaging/facturador.spec --noconfirm --clean

Write-Host ""
Write-Host "Build finished."
Write-Host "Executable: $Root\dist\Facturador\Facturador.exe"
