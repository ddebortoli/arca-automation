"""Main window for the Facturador AFIP desktop app."""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.styles import build_stylesheet
from ui.tab_certs import CertsTab
from ui.tab_config import ConfigTab
from ui.tab_run import RunTab
from core.config import get_certs_status, load_config, save_config
from src.bootstrap import build_afip_provider
from src.domain.exceptions import AfipValidationError


class AfipValidationWorker(QThread):
    """Validate AFIP configuration via FECompUltimoAutorizado (WSFE)."""

    ok = pyqtSignal(int)
    failed = pyqtSignal(int, str)

    def __init__(self, config: dict[str, str], request_id: int) -> None:
        super().__init__()
        self._config = config
        self._request_id = request_id

    def run(self) -> None:
        try:
            # validate_configuration reads WSFE values from os.environ.
            # Desktop config is stored in ~/.facturador/.env, so we apply
            # the current config values as env overrides for this thread.
            wsfe_keys = (
                "AFIP_WSFE_PUNTO_DE_VENTA",
                "AFIP_WSFE_TIPO_FACTURA",
                "AFIP_WSFE_CONCEPTO",
                "AFIP_WSFE_DOC_TIPO",
                "AFIP_WSFE_DOC_NRO",
                "AFIP_WSFE_CONDICION_IVA",
                "AFIP_WSFE_INVOICE_TYPE_LABEL",
                "AFIP_WSFE_CONCEPT_LABEL",
                "AFIP_WSFE_RECEIVER_LABEL",
            )
            for key in wsfe_keys:
                if key in self._config and self._config[key]:
                    os.environ[key] = self._config[key]

            provider = build_afip_provider(self._config)
            provider.validate_configuration()
            self.ok.emit(self._request_id)
        except AfipValidationError as exc:
            self.failed.emit(self._request_id, str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(self._request_id, f"{type(exc).__name__}: {exc}")


class MainWindow(QMainWindow):
    """Root window with sidebar navigation and 3 tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Facturador AFIP")
        self.setMinimumSize(860, 620)
        self.resize(980, 680)

        self._afip_validation_thread: AfipValidationWorker | None = None
        self._afip_validation_in_progress = False
        self._afip_validation_request_id = 0
        self._afip_validation_config_signature: str = ""
        self._afip_validation_pending_signature: str | None = None

        self._theme = load_config().get("THEME", "light")
        self._apply_theme()

        self._build_ui()
        self._update_status_dot()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Sidebar header (logo + names)
        sidebar_header = QWidget()
        sidebar_header.setObjectName("sidebar_header")
        header_layout = QHBoxLayout(sidebar_header)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(10)

        logo_widget = QWidget()
        logo_layout = QHBoxLayout(logo_widget)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(8)

        icon_lbl = QLabel("F")
        icon_lbl.setObjectName("logo_icon_label")
        icon_lbl.setFixedSize(28, 28)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        app_name = QLabel("Facturador")
        app_name.setObjectName("app_name_label")
        app_sub = QLabel("AFIP + MercadoPago")
        app_sub.setObjectName("app_sub_label")
        name_col.addWidget(app_name)
        name_col.addWidget(app_sub)

        logo_layout.addWidget(icon_lbl)
        logo_layout.addLayout(name_col)

        header_layout.addWidget(logo_widget)
        sidebar_layout.addWidget(sidebar_header)

        # Navigation
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 8, 0, 8)
        nav_layout.setSpacing(2)
        nav_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._nav_buttons: dict[str, QPushButton] = {}
        general_section = QLabel("General")
        general_section.setObjectName("nav_section_label")
        nav_layout.addWidget(general_section)

        for key, label in [
            ("config", "⚙  Configuración"),
            ("certs", "🔐  Certificados"),
        ]:
            btn = self._make_nav_btn(label, key)
            nav_layout.addWidget(btn)
            self._nav_buttons[key] = btn

        op_section = QLabel("Operación")
        op_section.setObjectName("nav_section_label")
        nav_layout.addWidget(op_section)

        run_btn = self._make_nav_btn("▶  Ejecutar", "run")
        nav_layout.addWidget(run_btn)
        self._nav_buttons["run"] = run_btn

        sidebar_layout.addWidget(nav_widget, stretch=1)

        # Theme toggle
        theme_widget = QWidget()
        theme_layout = QHBoxLayout(theme_widget)
        theme_layout.setContentsMargins(8, 6, 8, 6)
        self._theme_btn = QPushButton()
        self._theme_btn.setObjectName("theme_btn")
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._update_theme_btn_label()
        theme_layout.addWidget(self._theme_btn)
        sidebar_layout.addWidget(theme_widget)

        # Status dot
        status_widget = QWidget()
        status_widget.setObjectName("status_bar_widget")
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(16, 10, 16, 10)
        status_layout.setSpacing(6)
        self._dot_label = QLabel("●")
        self._dot_label.setStyleSheet("font-size: 12px; color: #888;")
        self._status_label = QLabel("Verificando…")
        self._status_label.setStyleSheet("font-size: 12px; color: #888;")
        status_layout.addWidget(self._dot_label)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()
        sidebar_layout.addWidget(status_widget)

        root.addWidget(sidebar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("content_area")

        self._tab_config = ConfigTab()
        self._tab_certs = CertsTab()
        self._tab_run = RunTab()

        self._stack.addWidget(self._tab_config)
        self._stack.addWidget(self._tab_certs)
        self._stack.addWidget(self._tab_run)

        self._tab_config.config_saved.connect(self._tab_run.refresh)
        self._tab_config.config_saved.connect(self._update_status_dot)

        root.addWidget(self._stack, stretch=1)
        self._switch_tab("config")

    def _make_nav_btn(self, label: str, key: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setObjectName("nav_btn")
        btn.clicked.connect(lambda _checked, k=key: self._switch_tab(k))
        return btn

    def _switch_tab(self, key: str) -> None:
        index = {"config": 0, "certs": 1, "run": 2}[key]
        self._stack.setCurrentIndex(index)

        for k, btn in self._nav_buttons.items():
            is_active = k == key
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _apply_theme(self) -> None:
        """Apply the current theme stylesheet to the whole window."""
        self.setStyleSheet(build_stylesheet(self._theme))

    def _toggle_theme(self) -> None:
        """Switch between light and dark themes and persist the choice."""
        self._theme = "dark" if self._theme == "light" else "light"
        self._apply_theme()
        self._update_theme_btn_label()
        self._update_status_dot()

        cfg = load_config()
        cfg["THEME"] = self._theme
        save_config(cfg)

    def _update_theme_btn_label(self) -> None:
        if self._theme == "dark":
            self._theme_btn.setText("☀  Modo claro")
            return
        self._theme_btn.setText("🌙  Modo oscuro")

    def _update_status_dot(self) -> None:
        cfg = load_config()
        certs = get_certs_status(cfg)

        tokens_and_files_ready = (
            bool(cfg.get("AFIP_CUIT"))
            and bool(cfg.get("MP_ACCESS_TOKEN"))
            and certs["key"]
            and certs["cert"]
        )

        if not tokens_and_files_ready:
            self._afip_validation_in_progress = False
            self._afip_validation_pending_signature = None
            self._dot_label.setStyleSheet("font-size: 12px; color: #BA7517;")
            self._status_label.setText("Configuración incompleta")
            self._status_label.setStyleSheet("font-size: 12px; color: #BA7517;")
            return

        signature = self._make_afip_validation_signature(cfg, certs)

        if self._afip_validation_in_progress:
            if signature != self._afip_validation_config_signature:
                self._afip_validation_pending_signature = signature
            return

        # Real readiness check: validate WSFE endpoint/config.
        self._afip_validation_request_id += 1
        self._afip_validation_config_signature = signature
        self._afip_validation_in_progress = True
        self._dot_label.setStyleSheet("font-size: 12px; color: #888;")
        self._status_label.setText("Validando AFIP…")
        self._status_label.setStyleSheet("font-size: 12px; color: #888;")

        thread = AfipValidationWorker(cfg, self._afip_validation_request_id)
        self._afip_validation_thread = thread
        thread.ok.connect(self._on_afip_validation_ok)  # type: ignore[arg-type]
        thread.failed.connect(self._on_afip_validation_failed)  # type: ignore[arg-type]
        thread.finished.connect(self._on_afip_validation_finished)  # type: ignore[arg-type]
        thread.start()

    @staticmethod
    def _make_afip_validation_signature(cfg: dict[str, str], certs: dict[str, bool]) -> str:
        wsfe_keys = (
            "AFIP_WSFE_PUNTO_DE_VENTA",
            "AFIP_WSFE_TIPO_FACTURA",
            "AFIP_WSFE_CONCEPTO",
            "AFIP_WSFE_DOC_TIPO",
            "AFIP_WSFE_DOC_NRO",
            "AFIP_WSFE_CONDICION_IVA",
            "AFIP_WSFE_INVOICE_TYPE_LABEL",
            "AFIP_WSFE_CONCEPT_LABEL",
            "AFIP_WSFE_RECEIVER_LABEL",
        )
        parts: list[str] = [
            str(cfg.get("AFIP_CUIT", "")),
            str(cfg.get("AFIP_CERT_PATH", "")),
            str(cfg.get("AFIP_KEY_PATH", "")),
            str(cfg.get("MP_ACCESS_TOKEN", "")),
            f"key={certs.get('key', False)}",
            f"cert={certs.get('cert', False)}",
        ]
        for k in wsfe_keys:
            parts.append(f"{k}={cfg.get(k, '')}")
        return "|".join(parts)

    def _on_afip_validation_finished(self) -> None:
        self._afip_validation_in_progress = False
        if self._afip_validation_pending_signature is not None:
            pending = self._afip_validation_pending_signature
            self._afip_validation_pending_signature = None
            # Only rerun if the config state is still consistent.
            self._update_status_dot()

    def _on_afip_validation_ok(self, request_id: int) -> None:
        if request_id != self._afip_validation_request_id:
            return
        self._dot_label.setStyleSheet("font-size: 12px; color: #1D9E75;")
        self._status_label.setText("Listo para facturar")
        self._status_label.setStyleSheet("font-size: 12px; color: #1D9E75;")

    def _on_afip_validation_failed(self, request_id: int, reason: str) -> None:
        if request_id != self._afip_validation_request_id:
            return
        self._dot_label.setStyleSheet("font-size: 12px; color: #BA7517;")
        self._status_label.setText(f"No listo para emitir: {reason}")
        self._status_label.setStyleSheet("font-size: 12px; color: #BA7517;")

