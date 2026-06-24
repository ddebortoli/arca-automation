"""Facturador AFIP desktop app (PyQt6).

Copyright (c) 2026 Damian Debortoli — https://www.ddebortoli.dev/
Contact: developer.ddebortoli@gmail.com

This app provides a guided UI to configure MercadoPago + AFIP and then
execute the existing pipeline in this repository.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Logfire's Pydantic plugin calls inspect.getsource and breaks in PyInstaller bundles.
if getattr(sys, "frozen", False):
    os.environ["PYDANTIC_DISABLE_PLUGINS"] = "true"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


def _configure_import_paths() -> None:
    """Expose desktop `ui`/`core` packages and repo `src` in dev and frozen builds."""
    if getattr(sys, "frozen", False):
        bundle_dir = Path(getattr(sys, "_MEIPASS"))
        candidates = (
            bundle_dir,
            bundle_dir / "desktop" / "facturador_pyqt6_app",
        )
        for path in candidates:
            if path.is_dir():
                path_str = str(path)
                if path_str not in sys.path:
                    sys.path.insert(0, path_str)
        return

    app_dir = Path(__file__).resolve().parent
    repo_root = app_dir.parents[1]
    for path in (app_dir, repo_root):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def main() -> None:
    """Application entrypoint."""
    _configure_import_paths()

    # Import at runtime because we modify `sys.path` to expose `ui.*` / `core.*`.
    from ui.main_window import MainWindow  # noqa: WPS433 (runtime import)

    app = QApplication(sys.argv)
    app.setApplicationName("Facturador")
    app.setOrganizationName("Facturador AFIP")
    high_dpi_attr = getattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps", None)
    if high_dpi_attr is not None:
        app.setAttribute(high_dpi_attr)

    window = MainWindow()
    window.show()

    smoke_ms_str = os.getenv("FACTURADOR_SMOKE_EXIT_MS", "").strip()
    if smoke_ms_str.isdigit():
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(int(smoke_ms_str), app.quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
