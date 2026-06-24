"""Tab: AFIP certificates management (generate CSR/key and import cert.crt)."""

from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.config import (
    CERTS_DIR,
    get_certs_status,
    import_cert_file,
    load_config,
    save_config,
)
from core.cert_generator import generate_key_and_csr
from core.paths import get_docs_dir
from ui.widgets import (
    AlertBanner,
    CardWidget,
    make_divider,
    make_field,
    make_section_header,
)


class GenerateWorker(QThread):
    """Background CSR/key generation using OpenSSL."""

    finished = pyqtSignal(str, str)  # key_path, csr_path
    error = pyqtSignal(str)

    def __init__(self, cuit: str) -> None:
        super().__init__()
        self._cuit = cuit

    def run(self) -> None:
        try:
            key_path, csr_path = generate_key_and_csr(self._cuit, CERTS_DIR)
            self.finished.emit(str(key_path), str(csr_path))
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class CertsTab(QWidget):
    """Certificates tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        cfg = load_config()
        self._key_path = cfg.get("AFIP_KEY_PATH", "")
        self._cert_path = cfg.get("AFIP_CERT_PATH", "")
        self._build_ui()
        self._refresh_status()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)  # type: ignore[attr-defined]

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(
            make_section_header(
                "Certificados AFIP",
                "Generá y luego copiá `cert.crt` (descargado desde AFIP) en la carpeta de configuración.",
            )
        )

        # Help section (PDF guide)
        docs_pdf_path = get_docs_dir() / "Guia_Facturacion_Electronica_ARCA.pdf"
        help_card = CardWidget()
        help_layout = QVBoxLayout()
        help_layout.setSpacing(10)

        help_layout.addWidget(
            make_section_header(
                "Ayuda",
                "Paso a paso para configurar AFIP y emitir Factura C (PDF).",
            )
        )

        if docs_pdf_path.exists():
            help_layout.addWidget(QLabel("Podés abrir la guía haciendo click en el botón:"))
            open_btn = QPushButton("Abrir guía (PDF)")
            open_btn.setObjectName("btn_secondary")

            def _open_docs() -> None:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs_pdf_path)))

            open_btn.clicked.connect(_open_docs)  # type: ignore[arg-type]
            help_layout.addWidget(open_btn)
        else:
            help_banner = AlertBanner("Guía PDF no encontrada en `docs/`.", kind="warning")
            help_layout.addWidget(help_banner)

        help_card.layout().addLayout(help_layout)
        layout.addWidget(help_card)

        card = CardWidget()
        card.layout().addWidget(self._build_step1())
        card.layout().addWidget(make_divider())
        card.layout().addWidget(self._build_step2())
        card.layout().addWidget(make_divider())
        card.layout().addWidget(self._build_step3())
        layout.addWidget(card)

        self._banner = AlertBanner()
        layout.addWidget(self._banner)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    def _build_step1(self) -> QWidget:
        wrapper = QWidget()
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        v.addWidget(make_section_header("Paso 1", "Generá tu clave privada y el CSR para AFIP."))

        row = QHBoxLayout()
        self._cuit_input = QLineEdit()
        self._cuit_input.setPlaceholderText("20-00000000-0")
        cfg = load_config()
        if cfg.get("AFIP_CUIT"):
            self._cuit_input.setText(cfg["AFIP_CUIT"])
        row.addWidget(self._cuit_input)

        self._gen_btn = QPushButton("Generar")
        self._gen_btn.setObjectName("btn_primary")
        self._gen_btn.clicked.connect(self._generate)  # type: ignore[arg-type]
        row.addWidget(self._gen_btn)

        self._gen_status = QLabel("")
        self._gen_status.setVisible(False)
        row.addWidget(self._gen_status)

        # Download widgets (hidden until CSR/key generation finishes)
        self._download_widget = QWidget()
        self._download_widget.setVisible(False)
        dl_layout = QHBoxLayout(self._download_widget)
        dl_layout.setContentsMargins(0, 0, 0, 0)
        dl_layout.setSpacing(8)

        self._dl_key_btn = QPushButton("Descargar private.key")
        self._dl_key_btn.setObjectName("btn_secondary")
        self._dl_key_btn.clicked.connect(self._download_key)  # type: ignore[arg-type]

        self._dl_csr_btn = QPushButton("Descargar solicitud.csr")
        self._dl_csr_btn.setObjectName("btn_secondary")
        self._dl_csr_btn.clicked.connect(self._download_csr)  # type: ignore[arg-type]

        dl_layout.addWidget(self._dl_key_btn)
        dl_layout.addWidget(self._dl_csr_btn)

        v.addLayout(row)
        v.addWidget(self._download_widget)

        v.addWidget(
            QLabel(
                "Esto generará automáticamente `private.key` y `solicitud.csr` dentro de `~/.facturador/certs/`."
            )
        )

        return wrapper

    def _build_step2(self) -> QWidget:
        wrapper = QWidget()
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        v.addWidget(make_section_header("Paso 2", "Subí el CSR a AFIP y descargá el certificado."))
        v.addWidget(
            QLabel(
                "Ingresá a AFIP → Administración de certificados digitales → "
                "subí `solicitud.csr`. AFIP te va a dar un archivo `.crt` para descargar."
            )
        )

        afip_btn = QPushButton("Ir a afip.gob.ar")
        afip_btn.setObjectName("btn_secondary")
        afip_btn.clicked.connect(self._open_afip_portal)  # type: ignore[arg-type]
        v.addWidget(afip_btn)

        return wrapper

    def _build_step3(self) -> QWidget:
        wrapper = QWidget()
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        v.addWidget(
            QLabel(
                "Cargá los archivos que ya tenés. La app los guarda en la carpeta de configuración."
            )
        )

        v.addWidget(make_section_header("Paso 3", "Cargá los archivos en la app"))

        # Private key selection
        v.addWidget(make_field("Clave privada  private.key", self._make_readonly_path_row("key")))
        key_pick_btn = QPushButton("Seleccionar")
        key_pick_btn.setObjectName("btn_secondary")
        key_pick_btn.clicked.connect(self._pick_key)  # type: ignore[arg-type]
        v.addWidget(key_pick_btn)

        # Certificate selection
        v.addWidget(make_field("Certificado AFIP  cert.crt", self._make_readonly_path_row("cert")))
        cert_pick_btn = QPushButton("Seleccionar")
        cert_pick_btn.setObjectName("btn_secondary")
        cert_pick_btn.clicked.connect(self._pick_cert)  # type: ignore[arg-type]
        v.addWidget(cert_pick_btn)

        return wrapper

    def _make_readonly_path_row(self, kind: str) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        display = QLineEdit()
        display.setReadOnly(True)
        display.setObjectName("readOnlyPath")
        display.setProperty("readOnly", True)
        display.setPlaceholderText("Sin archivo")
        if kind == "cert" and self._cert_path:
            display.setText(self._cert_path)
        if kind == "key" and self._key_path:
            display.setText(self._key_path)

        if kind == "cert":
            self._cert_display = display
        else:
            self._key_display = display

        h.addWidget(display, 1)
        return container

    def _generate(self) -> None:
        cuit = self._cuit_input.text().strip()
        if not cuit:
            self._gen_status.setText("⚠ Completá el CUIT primero.")
            self._gen_status.setStyleSheet("color: #BA7517;")
            self._gen_status.setVisible(True)
            return

        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("Generando…")

        self._worker = GenerateWorker(cuit)
        self._worker.finished.connect(self._on_generated)  # type: ignore[attr-defined]
        self._worker.error.connect(self._on_generate_error)  # type: ignore[attr-defined]
        self._worker.start()

    def _on_generated(self, key_path: str, csr_path: str) -> None:
        self._key_path = key_path
        self._generated_key_path = key_path
        self._generated_csr_path = csr_path
        self._key_display.setText(key_path)
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("Regenerar")

        self._gen_status.setText("✓ Archivos generados (private.key + solicitud.csr).")
        self._gen_status.setStyleSheet("color: #1D9E75;")
        self._gen_status.setVisible(True)
        self._download_widget.setVisible(True)

        cfg = load_config()
        cfg["AFIP_KEY_PATH"] = key_path
        save_config(cfg)
        self._refresh_status()

    def _on_generate_error(self, msg: str) -> None:
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("Generar")
        self._gen_status.setText(f"✗ Error generando CSR: {msg}")
        self._gen_status.setStyleSheet("color: #D85A30;")
        self._gen_status.setVisible(True)

    def _pick_cert(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar certificado AFIP",
            "",
            "Certificate Files (*.crt *.pem);;All Files (*)",
        )
        if not path:
            return

        dest = import_cert_file(path, "cert.crt")
        self._cert_path = dest
        self._cert_display.setText(dest)

        cfg = load_config()
        cfg["AFIP_CERT_PATH"] = dest
        save_config(cfg)
        self._refresh_status()

    def _pick_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar clave privada",
            "",
            "Key Files (*.key *.pem);;All Files (*)",
        )
        if not path:
            return

        dest = import_cert_file(path, "private.key")
        self._key_path = dest
        self._key_display.setText(dest)

        cfg = load_config()
        cfg["AFIP_KEY_PATH"] = dest
        save_config(cfg)
        self._refresh_status()

    def _download_key(self) -> None:
        if not hasattr(self, "_generated_key_path"):
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar private.key",
            "private.key",
            "PEM Files (*.key *.pem)",
        )
        if not dest:
            return
        shutil.copy2(self._generated_key_path, dest)

    def _download_csr(self) -> None:
        if not hasattr(self, "_generated_csr_path"):
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar solicitud.csr",
            "solicitud.csr",
            "CSR Files (*.csr *.pem)",
        )
        if not dest:
            return
        shutil.copy2(self._generated_csr_path, dest)

    def _open_afip_portal(self) -> None:
        QDesktopServices.openUrl(QUrl("https://auth.afip.gob.ar/contribuyente_/"))

    def _refresh_status(self) -> None:
        cfg = load_config()
        certs_status = get_certs_status(cfg)

        if certs_status["key"] and certs_status["cert"]:
            self._banner.setText("✓ Ambos archivos presentes. Podés emitir facturas.")
            self._banner.setObjectName("alert_success")
            return

        if certs_status["key"] and not certs_status["cert"]:
            self._banner.setText(
                "Falta el certificado de AFIP. No podés emitir facturas hasta completar el paso 3."
            )
            self._banner.setObjectName("alert_warning")
            return

        self._banner.setText(
            "Falta el certificado de AFIP. No podés emitir facturas hasta completar el paso 3."
        )
        self._banner.setObjectName("alert_warning")
