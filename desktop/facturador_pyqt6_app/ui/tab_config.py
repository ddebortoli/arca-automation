"""Tab: configuration for AFIP + MercadoPago + approval mode."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl, pyqtSignal, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.config import load_config, save_config
from ui.widgets import (
    AlertBanner,
    CardWidget,
    SecretLineEdit,
    make_divider,
    make_field,
    make_section_header,
)


class ConfigTab(QWidget):
    """Configuration form persisted in `~/.facturador/.env`."""

    config_saved = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._approval_mode: str = "auto"

        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)  # type: ignore[attr-defined]

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(20)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        content_layout.addWidget(
            make_section_header("AFIP / ARCA", "Datos para emitir facturas electrónicas.")
        )
        afip_card = CardWidget()
        row_afip = QHBoxLayout()
        row_afip.setSpacing(12)

        self.afip_cuit = QLineEdit()
        self.afip_cuit.setPlaceholderText("20-00000000-0")
        row_afip.addWidget(make_field("CUIT", self.afip_cuit))

        #self.afip_token = SecretLineEdit("AFIP_ACCESS_TOKEN")
        #row_afip.addWidget(make_field("Access token", self.afip_token))

        afip_card.layout().addLayout(row_afip)
        content_layout.addWidget(afip_card)

        content_layout.addWidget(make_section_header("MercadoPago", "Credenciales para obtener movimientos."))
        mp_card = CardWidget()
        row_mp = QHBoxLayout()
        row_mp.setSpacing(12)

        self.mp_user_id = QLineEdit()
        self.mp_user_id.setPlaceholderText("ID de usuario")
        row_mp.addWidget(make_field("User ID", self.mp_user_id))

        self.mp_token = SecretLineEdit("APP_USR-...")
        row_mp.addWidget(make_field("Access token", self.mp_token))
        mp_card.layout().addLayout(row_mp)

        # Help section (PDF guide)
        docs_pdf_path = Path(__file__).resolve().parents[3] / "docs" / "Guia_Integracion_MercadoPago.pdf"
        mp_card.layout().addWidget(make_divider())
        help_layout = QVBoxLayout()
        help_layout.setSpacing(10)
        help_layout.addWidget(
            make_section_header(
                "Ayuda",
                "Paso a paso para integrar MercadoPago (PDF).",
            )
        )

        if docs_pdf_path.exists():
            help_layout.addWidget(
                QLabel("Podés abrir la guía haciendo click en el botón:")
            )
            open_btn = QPushButton("Abrir guía (PDF)")
            open_btn.setObjectName("btn_secondary")

            def _open_docs() -> None:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs_pdf_path)))

            open_btn.clicked.connect(_open_docs)  # type: ignore[arg-type]
            help_layout.addWidget(open_btn)
        else:
            help_layout.addWidget(AlertBanner("Guía PDF no encontrada en `docs/`.", kind="warning"))

        mp_card.layout().addLayout(help_layout)
        content_layout.addWidget(mp_card)

        content_layout.addWidget(
            make_section_header(
                "WSFE (Factura C)",
                "Valores para PtoVta/CbteTipo y campos del comprobante.",
            )
        )
        wsfe_card = CardWidget()
        wsfe_layout = QVBoxLayout()
        wsfe_layout.setSpacing(12)

        row_wsfe_1 = QHBoxLayout()
        row_wsfe_1.setSpacing(12)
        self.wsfe_punto_de_venta = QLineEdit()
        self.wsfe_punto_de_venta.setPlaceholderText("2")
        row_wsfe_1.addWidget(make_field("PtoVta", self.wsfe_punto_de_venta))

        self.wsfe_tipo_factura = QLineEdit()
        self.wsfe_tipo_factura.setPlaceholderText("11")
        row_wsfe_1.addWidget(make_field("CbteTipo", self.wsfe_tipo_factura))
        wsfe_layout.addLayout(row_wsfe_1)

        row_wsfe_2 = QHBoxLayout()
        row_wsfe_2.setSpacing(12)
        self.wsfe_concepto = QLineEdit()
        self.wsfe_concepto.setPlaceholderText("2")
        row_wsfe_2.addWidget(make_field("Concepto", self.wsfe_concepto))

        self.wsfe_doc_tipo = QLineEdit()
        self.wsfe_doc_tipo.setPlaceholderText("99")
        row_wsfe_2.addWidget(make_field("DocTipo", self.wsfe_doc_tipo))
        wsfe_layout.addLayout(row_wsfe_2)

        row_wsfe_3 = QHBoxLayout()
        row_wsfe_3.setSpacing(12)
        self.wsfe_doc_nro = QLineEdit()
        self.wsfe_doc_nro.setPlaceholderText("0")
        row_wsfe_3.addWidget(make_field("DocNro", self.wsfe_doc_nro))

        self.wsfe_condicion_iva = QLineEdit()
        self.wsfe_condicion_iva.setPlaceholderText("5")
        row_wsfe_3.addWidget(make_field("CondicionIVAReceptorId", self.wsfe_condicion_iva))
        wsfe_layout.addLayout(row_wsfe_3)

        row_wsfe_4 = QHBoxLayout()
        row_wsfe_4.setSpacing(12)
        self.wsfe_invoice_type_label = QLineEdit()
        self.wsfe_invoice_type_label.setPlaceholderText("Factura C")
        row_wsfe_4.addWidget(make_field("Label factura", self.wsfe_invoice_type_label))

        self.wsfe_concept_label = QLineEdit()
        self.wsfe_concept_label.setPlaceholderText("Servicios")
        row_wsfe_4.addWidget(make_field("Label concepto", self.wsfe_concept_label))
        wsfe_layout.addLayout(row_wsfe_4)

        row_wsfe_5 = QHBoxLayout()
        row_wsfe_5.setSpacing(12)
        self.wsfe_receiver_label = QLineEdit()
        self.wsfe_receiver_label.setPlaceholderText("Consumidor Final")
        row_wsfe_5.addWidget(make_field("Label receptor", self.wsfe_receiver_label))
        wsfe_layout.addLayout(row_wsfe_5)

        wsfe_card.layout().addLayout(wsfe_layout)
        content_layout.addWidget(wsfe_card)

        content_layout.addWidget(make_section_header("Modo de aprobación", "auto o telegram."))
        approval_card = CardWidget()
        toggle_group = QWidget()
        toggle_layout = QHBoxLayout(toggle_group)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(0)
        toggle_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.btn_auto = QPushButton("Automático")
        self.btn_auto.setObjectName("toggle_btn_left")
        self.btn_auto.clicked.connect(lambda: self._set_mode("auto"))  # type: ignore[arg-type]
        toggle_layout.addWidget(self.btn_auto)

        self.btn_telegram = QPushButton("Telegram")
        self.btn_telegram.setObjectName("toggle_btn_right")
        self.btn_telegram.clicked.connect(lambda: self._set_mode("telegram"))  # type: ignore[arg-type]
        toggle_layout.addWidget(self.btn_telegram)

        approval_card.layout().addWidget(toggle_group)

        self._telegram_widget = QWidget()
        tg_layout = QVBoxLayout(self._telegram_widget)
        tg_layout.setContentsMargins(0, 8, 0, 0)
        tg_layout.setSpacing(12)
        tg_layout.addWidget(make_divider())

        # Help section (PDF guide)
        docs_pdf_path = (
            Path(__file__).resolve().parents[3]
            / "docs"
            / "Guia_Configuracion_Bot_Telegram.pdf"
        )
        tg_layout.addWidget(
            make_section_header(
                "Ayuda",
                "Paso a paso para configurar el bot de Telegram (PDF).",
            )
        )
        if docs_pdf_path.exists():
            tg_layout.addWidget(
                QLabel("Podés abrir la guía haciendo click en el botón:")
            )
            open_btn = QPushButton("Abrir guía (PDF)")
            open_btn.setObjectName("btn_secondary")

            def _open_docs() -> None:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs_pdf_path)))

            open_btn.clicked.connect(_open_docs)  # type: ignore[arg-type]
            tg_layout.addWidget(open_btn)
        else:
            tg_layout.addWidget(
                AlertBanner("Guía PDF no encontrada en `docs/`.", kind="warning")
            )

        tg_row = QHBoxLayout()
        tg_row.setSpacing(12)
        self.tg_token = SecretLineEdit("123456:ABCdef...")
        tg_row.addWidget(make_field("Bot token", self.tg_token))

        self.tg_chat_id = QLineEdit()
        self.tg_chat_id.setPlaceholderText("-1001234567890")
        tg_row.addWidget(make_field("Chat ID", self.tg_chat_id))
        tg_layout.addLayout(tg_row)

        approval_card.layout().addWidget(self._telegram_widget)
        content_layout.addWidget(approval_card)

        content_layout.addWidget(make_section_header("Observabilidad (opcional)", "Usa logfire para trazas detalladas."))
        obs_card = CardWidget()
        self._logfire_check = QCheckBox("Activar Logfire")
        obs_card.layout().addWidget(self._logfire_check)

        self._logfire_widget = QWidget()
        lf_layout = QVBoxLayout(self._logfire_widget)
        lf_layout.setContentsMargins(0, 8, 0, 0)
        self.logfire_token = SecretLineEdit("pylf_...")
        lf_layout.addWidget(make_field("Logfire token", self.logfire_token))
        obs_card.layout().addWidget(self._logfire_widget)
        self._logfire_widget.setVisible(False)

        self._logfire_check.stateChanged.connect(self._toggle_logfire)  # type: ignore[arg-type]
        content_layout.addWidget(obs_card)

        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 10, 24, 10)

        self._save_status = QLabel("")
        self._save_status.setStyleSheet("font-size:12px; color:#888;")
        footer_layout.addWidget(self._save_status)
        footer_layout.addStretch()

        save_btn = QPushButton("Guardar cambios")
        save_btn.setObjectName("btn_primary")
        save_btn.clicked.connect(self._save)  # type: ignore[arg-type]
        footer_layout.addWidget(save_btn)

        outer.addWidget(footer)

    def _set_mode(self, mode: str) -> None:
        self._approval_mode = mode
        telegram_visible = mode == "telegram"
        self._telegram_widget.setVisible(telegram_visible)
        self.tg_token.setEnabled(telegram_visible)  # type: ignore[arg-type]
        self.tg_chat_id.setEnabled(telegram_visible)

        self.btn_auto.setProperty("active", mode == "auto")
        self.btn_telegram.setProperty("active", mode == "telegram")
        # Force Qt stylesheet updates for property changes.
        for btn in (self.btn_auto, self.btn_telegram):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _toggle_logfire(self, state: int) -> None:
        enabled = bool(state)
        self._logfire_widget.setVisible(enabled)
        self.logfire_token.setEnabled(enabled)  # type: ignore[arg-type]

    def _load(self) -> None:
        cfg = load_config()

        self.afip_cuit.setText(cfg.get("AFIP_CUIT", ""))
        #self.afip_token.setText(cfg.get("AFIP_ACCESS_TOKEN", ""))  # type: ignore[attr-defined]
        self.mp_user_id.setText(cfg.get("MP_USER_ID", ""))
        self.mp_token.setText(cfg.get("MP_ACCESS_TOKEN", ""))  # type: ignore[arg-type]

        self.wsfe_punto_de_venta.setText(cfg.get("AFIP_WSFE_PUNTO_DE_VENTA", ""))  # type: ignore[attr-defined]
        self.wsfe_tipo_factura.setText(cfg.get("AFIP_WSFE_TIPO_FACTURA", ""))  # type: ignore[attr-defined]
        self.wsfe_concepto.setText(cfg.get("AFIP_WSFE_CONCEPTO", ""))  # type: ignore[attr-defined]
        self.wsfe_doc_tipo.setText(cfg.get("AFIP_WSFE_DOC_TIPO", ""))  # type: ignore[attr-defined]
        self.wsfe_doc_nro.setText(cfg.get("AFIP_WSFE_DOC_NRO", ""))  # type: ignore[attr-defined]
        self.wsfe_condicion_iva.setText(cfg.get("AFIP_WSFE_CONDICION_IVA", ""))  # type: ignore[attr-defined]
        self.wsfe_invoice_type_label.setText(cfg.get("AFIP_WSFE_INVOICE_TYPE_LABEL", ""))  # type: ignore[attr-defined]
        self.wsfe_concept_label.setText(cfg.get("AFIP_WSFE_CONCEPT_LABEL", ""))  # type: ignore[attr-defined]
        self.wsfe_receiver_label.setText(cfg.get("AFIP_WSFE_RECEIVER_LABEL", ""))  # type: ignore[attr-defined]

        mode = cfg.get("APPROVAL_MODE", "auto")
        self._set_mode(mode)
        if mode == "telegram":
            self.tg_token.setText(cfg.get("TELEGRAM_BOT_TOKEN", ""))  # type: ignore[arg-type]
            self.tg_chat_id.setText(cfg.get("TELEGRAM_CHAT_ID", ""))

        backend = cfg.get("OBSERVABILITY_BACKEND", "stdio")
        if backend == "logfire":
            self._logfire_check.setChecked(True)
            self.logfire_token.setText(cfg.get("LOGFIRE_TOKEN", ""))  # type: ignore[arg-type]

    def _save(self) -> None:
        data = {
            "AFIP_CUIT": self.afip_cuit.text().strip(),
            #"AFIP_ACCESS_TOKEN": self.afip_token.text().strip(),
            "MP_ACCESS_TOKEN": self.mp_token.text().strip(),  # type: ignore[union-attr]
            "MP_USER_ID": self.mp_user_id.text().strip(),
            "APPROVAL_MODE": self._approval_mode,
            "TELEGRAM_BOT_TOKEN": self.tg_token.text().strip(),  # type: ignore[union-attr]
            "TELEGRAM_CHAT_ID": self.tg_chat_id.text().strip(),
            "OBSERVABILITY_BACKEND": "logfire" if self._logfire_check.isChecked() else "stdio",
            "LOGFIRE_TOKEN": self.logfire_token.text().strip(),  # type: ignore[union-attr]
            "AFIP_WSFE_PUNTO_DE_VENTA": self.wsfe_punto_de_venta.text().strip(),  # type: ignore[attr-defined]
            "AFIP_WSFE_TIPO_FACTURA": self.wsfe_tipo_factura.text().strip(),  # type: ignore[attr-defined]
            "AFIP_WSFE_CONCEPTO": self.wsfe_concepto.text().strip(),  # type: ignore[attr-defined]
            "AFIP_WSFE_DOC_TIPO": self.wsfe_doc_tipo.text().strip(),  # type: ignore[attr-defined]
            "AFIP_WSFE_DOC_NRO": self.wsfe_doc_nro.text().strip(),  # type: ignore[attr-defined]
            "AFIP_WSFE_CONDICION_IVA": self.wsfe_condicion_iva.text().strip(),  # type: ignore[attr-defined]
            "AFIP_WSFE_INVOICE_TYPE_LABEL": self.wsfe_invoice_type_label.text().strip(),  # type: ignore[attr-defined]
            "AFIP_WSFE_CONCEPT_LABEL": self.wsfe_concept_label.text().strip(),  # type: ignore[attr-defined]
            "AFIP_WSFE_RECEIVER_LABEL": self.wsfe_receiver_label.text().strip(),  # type: ignore[attr-defined]
        }
        save_config(data)
        self._save_status.setText("✓  Guardado")
        self._save_status.setStyleSheet("font-size:12px; color:#1D9E75;")
        self.config_saved.emit()

