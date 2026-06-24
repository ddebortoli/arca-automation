#!/usr/bin/env bash
# Build the Facturador AFIP desktop app with PyInstaller.
#
# Output:
#   macOS:   dist/Facturador.app
#   Linux:   dist/Facturador/Facturador
#   Windows: dist/Facturador/Facturador.exe  (run via Git Bash or WSL)
#
# Requirements:
#   - uv
#   - OpenSSL available on PATH (AFIP signing uses the `openssl` CLI)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Syncing dependencies (including PyInstaller)"
uv sync --group dev

echo "==> Building desktop executable"
uv run pyinstaller packaging/facturador.spec --noconfirm --clean

echo ""
echo "Build finished."
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "App bundle: $ROOT/dist/Facturador.app"
  echo "Open with: open dist/Facturador.app"
elif [[ "$(uname -s)" == "MINGW"* || "$(uname -s)" == "MSYS"* || "$(uname -s)" == "CYGWIN"* ]]; then
  echo "Executable: $ROOT/dist/Facturador/Facturador.exe"
else
  echo "Executable: $ROOT/dist/Facturador/Facturador"
fi
