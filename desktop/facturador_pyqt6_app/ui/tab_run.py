"""Tab: run facturation and show logs/stats."""

from __future__ import annotations

import logging
import os
from logging import Handler, LogRecord

from PyQt6.QtCore import QDateTime, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config import ENV_FILE, get_certs_status, load_config
from src.bootstrap import build_repository
from src.pipeline import run_payment_pipeline_safe, start_telegram_bot_thread
from ui.widgets import CardWidget, make_section_header, make_stat_card


def _classify_level(line: str) -> str:
    """Classify log lines to color in UI."""
    lowered = line.lower()
    if "error" in lowered or "exception" in lowered or "traceback" in lowered:
        return "err"
    if "warn" in lowered or "warning" in lowered:
        return "warn"
    if lowered.startswith("✓") or " ok" in lowered:
        return "ok"
    return ""


class _QtLogHandler(Handler):
    """Forward logging records to a Qt signal."""

    preserve_on_reconfigure = True

    def __init__(self, emit_line) -> None:
        super().__init__()
        self._emit_line = emit_line
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s"))
        self.setLevel(logging.INFO)

    def emit(self, record: LogRecord) -> None:
        message = self.format(record)
        if not message:
            return

        level = record.levelname.lower()
        if level in {"error", "critical"}:
            style = "err"
        elif level == "warning":
            style = "warn"
        else:
            style = "raw"
        self._emit_line(message, style)


class RunnerWorker(QThread):
    """Run the payment pipeline in-process."""

    log_line = pyqtSignal(str, str)  # message, level
    stats_ready = pyqtSignal(int, int, int)
    finished = pyqtSignal()

    def run(self) -> None:
        """Execute the pipeline."""
        cfg = load_config()
        approval_mode = cfg.get("APPROVAL_MODE", "auto")

        os.environ["ARC_ENV_FILE"] = str(ENV_FILE)

        handler = _QtLogHandler(self.log_line.emit)
        root = logging.getLogger()
        for existing in list(root.handlers):
            if isinstance(existing, _QtLogHandler):
                root.removeHandler(existing)
        root.addHandler(handler)
        for logger_name in ("httpx", "src"):
            logging.getLogger(logger_name).setLevel(logging.INFO)
        bot_thread = None

        try:
            if approval_mode == "telegram":
                bot_result = start_telegram_bot_thread()
                bot_thread = bot_result.thread
                if bot_result.reused_existing:
                    self.log_line.emit(
                        "Bot de Telegram ya activo — reutilizando conexión.",
                        "ok",
                    )
                else:
                    self.log_line.emit("Iniciando Telegram bot…", "ok")

            run_payment_pipeline_safe()
        except Exception as exc:  # noqa: BLE001
            self.log_line.emit(f"Error ejecutando: {exc}", "err")
        finally:
            if bot_thread is None or not bot_thread.is_alive():
                root.removeHandler(handler)
            try:
                repository = build_repository()
                total, billed, pending = repository.count_payment_stats()
            except Exception:  # noqa: BLE001
                total, billed, pending = 0, 0, 0
            self.stats_ready.emit(total, billed, pending)
            if bot_thread is not None and bot_thread.is_alive():
                self.log_line.emit(
                    "Telegram bot sigue activo en segundo plano.",
                    "",
                )
            self.finished.emit()


class RunTab(QWidget):
    """Run screen: logs + execution stats."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: RunnerWorker | None = None
        self._build_ui()
        self._check_readiness()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        header_row.addWidget(
            make_section_header(
                "Ejecutar facturación",
                "Obtiene movimientos de MercadoPago y emite las facturas pendientes en AFIP.",
            ),
            1,
        )

        self._run_btn = QPushButton("▶  Ejecutar ahora")
        self._run_btn.setObjectName("btn_primary")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._run)  # type: ignore[arg-type]
        header_row.addWidget(self._run_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)

        self._stat_total_card, self._stat_total = make_stat_card("Movimientos", "—")
        self._stat_billed_card, self._stat_billed = make_stat_card("Ya facturados", "—", "green")

        stats_row.addWidget(self._stat_total_card)
        stats_row.addWidget(self._stat_billed_card)
        layout.addLayout(stats_row)

        log_card = CardWidget()
        log_header = QHBoxLayout()
        log_title = QLabel("Log de ejecución")
        log_title.setObjectName("section_title")
        log_header.addWidget(log_title)
        log_header.addStretch()

        clear_btn = QPushButton("Limpiar")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self._clear_log)  # type: ignore[arg-type]
        log_header.addWidget(clear_btn)

        log_card.layout().addLayout(log_header)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(220)
        log_card.layout().addWidget(self._log, 1)

        layout.addWidget(log_card, 1)

        self._not_ready_label = QLabel("")
        self._not_ready_label.setVisible(False)
        self._not_ready_label.setObjectName("alert_warning")
        layout.addWidget(self._not_ready_label)

    def _check_readiness(self) -> None:
        cfg = load_config()
        certs = get_certs_status(cfg)

        missing: list[str] = []
        if not cfg.get("AFIP_CUIT"):
            missing.append("CUIT de AFIP")
        if not cfg.get("MP_ACCESS_TOKEN"):
            missing.append("token de MercadoPago")
        if not certs["key"]:
            missing.append("clave privada")
        if not certs["cert"]:
            missing.append("certificado de AFIP")
        if cfg.get("DATABASE_BACKEND", "sqlite") == "postgres" and not cfg.get("DATABASE_URL"):
            missing.append("connection string de PostgreSQL")

        if missing:
            self._run_btn.setEnabled(False)
            items = ", ".join(missing)
            self._not_ready_label.setText(f"⚠ Configuración incompleta — falta: {items}.")
            self._not_ready_label.setVisible(True)
            return

        self._run_btn.setEnabled(True)
        self._not_ready_label.setVisible(False)

    def _run(self) -> None:
        self._check_readiness()
        if not self._run_btn.isEnabled():
            return

        if self._worker and self._worker.isRunning():
            return

        self._run_btn.setEnabled(False)
        self._run_btn.setText("Ejecutando…")

        self._append_log(
            f"── Nueva ejecución  {QDateTime.currentDateTime().toString('hh:mm:ss')} ──",
            "",
        )

        self._worker = RunnerWorker()
        self._worker.log_line.connect(self._append_log)  # type: ignore[arg-type]
        self._worker.stats_ready.connect(self._update_stats)  # type: ignore[arg-type]
        self._worker.finished.connect(self._on_finished)  # type: ignore[arg-type]
        self._worker.start()

    def _on_finished(self) -> None:
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  Ejecutar ahora")

    def _append_log(self, message: str, level: str) -> None:
        if level == "raw":
            line = message
        else:
            ts = QDateTime.currentDateTime().toString("hh:mm:ss")
            line = f"[{ts}]  {message}"

        colors = {
            "ok": "#1D9E75",
            "warn": "#BA7517",
            "err": "#D85A30",
            "raw": "#555555",
            "": "#555555",
        }
        color = colors.get(level, "#555555")

        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(line + "\n", fmt)
        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()

    def _update_stats(self, total: int, billed: int, pending: int) -> None:
        self._stat_total.setText(str(total))
        self._stat_billed.setText(str(billed))

    def _clear_log(self) -> None:
        self._log.clear()

    def refresh(self) -> None:
        """Re-check readiness after config/certs changes."""
        self._check_readiness()
