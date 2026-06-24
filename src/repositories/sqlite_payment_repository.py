"""SQLite-backed payment repository."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Generator

from ..domain.models import (
    IssuedInvoice,
    MercadoPagoPayment,
    PaymentRecord,
    PaymentStatus,
)
from .common import (
    COUNT_STATS,
    SELECT_BY_STATUS,
    SELECT_PAYMENT,
    SQLITE_DDL,
    row_to_payment_record,
    utcnow,
)


class SqlitePaymentRepository:
    """SQLite store tracking the processing status of MercadoPago payments."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def filter_new_payments(self, payments: list[MercadoPagoPayment]) -> list[MercadoPagoPayment]:
        """Return payments whose IDs are not yet present in the database."""
        if not payments:
            return []

        ids = [p.id for p in payments]
        placeholders = ",".join("?" * len(ids))

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT mp_payment_id FROM payments WHERE mp_payment_id IN ({placeholders})",
                ids,
            ).fetchall()

        existing = {row[0] for row in rows}
        return [p for p in payments if p.id not in existing]

    def list_fetched(self) -> list[MercadoPagoPayment]:
        """Return payments awaiting approval submission or auto-invoicing."""
        return self._list_payments_by_status("fetched")

    def get_payment(self, mp_payment_id: int) -> PaymentRecord | None:
        """Return a payment by MercadoPago ID, if it exists."""
        with self._connect() as conn:
            row = conn.execute(
                SELECT_PAYMENT.format(placeholder="?"),
                (mp_payment_id,),
            ).fetchone()

        if row is None:
            return None

        return row_to_payment_record(row)

    def insert_fetched(self, payments: list[MercadoPagoPayment]) -> None:
        """Persist *payments* with status ``fetched``."""
        now = utcnow()
        rows = [
            (
                p.id,
                "fetched",
                float(p.transaction_amount),
                p.date_created.isoformat(),
                now,
                now,
            )
            for p in payments
        ]
        with self._connect() as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO payments
                   (mp_payment_id, status, transaction_amount, date_created, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                rows,
            )

    def mark_pending_approval(self, mp_payment_id: int) -> None:
        """Transition payment to ``pending_approval``."""
        self._update_status(mp_payment_id, "pending_approval")

    def mark_fetched(self, mp_payment_id: int) -> None:
        """Return payment to ``fetched`` for a future approval cycle."""
        self._update_status(mp_payment_id, "fetched")

    def mark_issued(self, mp_payment_id: int, invoice: IssuedInvoice) -> None:
        """Transition payment to ``issued`` and store the resulting CAE."""
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE payments
                   SET status='issued', cae=?, cae_expiry=?, invoice_number=?, updated_at=?
                   WHERE mp_payment_id=?""",
                (
                    invoice.cae,
                    invoice.cae_expiry,
                    invoice.invoice_number,
                    now,
                    mp_payment_id,
                ),
            )

    def mark_failed(self, mp_payment_id: int, error: str) -> None:
        """Transition payment to ``failed`` and store the error description."""
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE payments
                   SET status='failed', error_message=?, updated_at=?
                   WHERE mp_payment_id=?""",
                (error, now, mp_payment_id),
            )

    def mark_postponed(self, mp_payment_id: int, error: str) -> None:
        """Transition payment to ``fetched`` and store an error for retry."""
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE payments
                   SET status='fetched', error_message=?, updated_at=?
                   WHERE mp_payment_id=?""",
                (error, now, mp_payment_id),
            )

    def mark_rejected(self, mp_payment_id: int, reason: str = "Rechazado por usuario") -> None:
        """Transition payment to ``rejected`` (terminal, no retries)."""
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE payments
                   SET status='rejected', error_message=?, updated_at=?
                   WHERE mp_payment_id=?""",
                (reason, now, mp_payment_id),
            )

    def count_payment_stats(self) -> tuple[int, int, int]:
        """Return ``(total, billed, pending)`` payment counts."""
        with self._connect() as conn:
            row = conn.execute(COUNT_STATS).fetchone()
        if row is None:
            return 0, 0, 0
        return int(row[0]), int(row[1]), int(row[2])

    def _list_payments_by_status(self, status: PaymentStatus) -> list[MercadoPagoPayment]:
        with self._connect() as conn:
            rows = conn.execute(
                SELECT_BY_STATUS.format(placeholder="?"),
                (status,),
            ).fetchall()

        return [
            MercadoPagoPayment(
                id=row[0],
                transaction_amount=Decimal(str(row[1])),
                date_created=row[2],
                status=status,
            )
            for row in rows
        ]

    def _update_status(self, mp_payment_id: int, status: PaymentStatus) -> None:
        now = utcnow()
        with self._connect() as conn:
            conn.execute(
                "UPDATE payments SET status=?, updated_at=? WHERE mp_payment_id=?",
                (status, now, mp_payment_id),
            )

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(SQLITE_DDL)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
