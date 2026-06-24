# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Facturador AFIP desktop app."""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

spec_dir = Path(SPECPATH)
repo_root = spec_dir.parent
app_dir = repo_root / "desktop" / "facturador_pyqt6_app"

block_cipher = None

hiddenimports = collect_submodules("src")
hiddenimports += [
    "ui.main_window",
    "ui.tab_config",
    "ui.tab_run",
    "ui.tab_certs",
    "ui.styles",
    "ui.widgets",
    "core.config",
    "core.paths",
    "core.cert_generator",
]

datas = [(str(repo_root / "docs"), "docs")]
binaries: list[tuple[str, str]] = []

for package in ("PyQt6", "zeep", "psycopg", "cryptography", "httpx"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [str(app_dir / "main.py")],
    pathex=[str(repo_root), str(app_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "tkinter", "logfire"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Facturador",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Facturador",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Facturador.app",
        icon=None,
        bundle_identifier="ar.facturador.afip",
    )
