"""Facturador AFIP desktop app (PyQt6).

This app provides a guided UI to configure MercadoPago + AFIP and then
execute the existing pipeline in this repository.
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication


def main() -> None:
    """Application entrypoint."""
    # Ensure `ui.*` / `core.*` inside this folder and repo `src.*` are importable.
    app_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(app_dir))

    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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
        # Useful to validate imports without keeping Qt running forever.
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(int(smoke_ms_str), app.quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

