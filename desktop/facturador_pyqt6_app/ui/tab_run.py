"""Tab: run facturation and show logs/stats."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

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
from ui.widgets import CardWidget, make_section_header, make_stat_card


def _repo_root() -> Path:
    """Compute repository root from this file location."""
    # .../desktop/facturador_pyqt6_app/ui/tab_run.py -> parents[3] is repo root.
    return Path(__file__).resolve().parents[3]


def _count_payment_statuses(db_path: Path) -> tuple[int, int, int]:
    """Return (total, billed, pending) from sqlite payments table."""
    if not db_path.exists():
        return 0, 0, 0

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        total = int(cur.execute("SELECT COUNT(*) FROM payments").fetchone()[0])
        billed = int(cur.execute("SELECT COUNT(*) FROM payments WHERE status='issued'").fetchone()[0])
        pending = int(
            cur.execute(
                """
                SELECT COUNT(*) FROM payments
                WHERE status IN ('fetched', 'pending_approval')
                """
            ).fetchone()[0]
        )
        return total, billed, pending
    finally:
        conn.close()


def _classify_level(line: str) -> str:
    """Classify log lines to color in UI."""
    lowered = line.lower()
    if "error" in lowered or "exception" in lowered or "traceback" in lowered:
        return "err"
    if "warn" in lowered or "warning" in lowered:
        return "warn"
    if lowered.startswith("✓") or "ok" in lowered:
        return "ok"
    return ""


class RunnerWorker(QThread):
    """Run `uv run main.py` (and telegram bot if needed)."""

    log_line = pyqtSignal(str, str)  # message, level
    stats_ready = pyqtSignal(int, int, int)
    finished = pyqtSignal()

    def run(self) -> None:
        """Execute the pipeline."""
        cfg = load_config()
        approval_mode = cfg.get("APPROVAL_MODE", "auto")

        env = os.environ.copy()
        env["ARC_ENV_FILE"] = str(ENV_FILE)

        root = _repo_root()
        main_cmd = ["uv", "run", "main.py"]

        bot_proc: subprocess.Popen[str] | None = None
        try:
            if approval_mode == "telegram":
                bot_cmd = ["uv", "run", "telegram_bot.py"]
                bot_proc = subprocess.Popen(
                    bot_cmd,
                    cwd=str(root),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self.log_line.emit("Iniciando Telegram bot…", "")

            proc = subprocess.Popen(
                main_cmd,
                cwd=str(root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip("\n")
                if line:
                    self.log_line.emit(line, _classify_level(line))

            proc.wait()
        except Exception as exc:  # noqa: BLE001
            self.log_line.emit(f"Error ejecutando: {exc}", "err")
        finally:
            # Keep bot running if it was started; user can close the app.
            payments_db = root / "payments.db"
            total, billed, pending = _count_payment_statuses(payments_db)
            self.stats_ready.emit(total, billed, pending)
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
        #self._stat_pending_card, self._stat_pending = make_stat_card("Pendientes", "—", "amber")

        stats_row.addWidget(self._stat_total_card)
        stats_row.addWidget(self._stat_billed_card)
        #stats_row.addWidget(self._stat_pending_card)
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
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")
        line = f"[{ts}]  {message}"

        colors = {
            "ok": "#1D9E75",
            "warn": "#BA7517",
            "err": "#D85A30",
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
        #self._stat_pending.setText(str(pending))

    def _clear_log(self) -> None:
        self._log.clear()

    def refresh(self) -> None:
        """Re-check readiness after config/certs changes."""
        self._check_readiness()

