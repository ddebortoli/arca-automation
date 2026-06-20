import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Generator

from ..domain.models import IssuedInvoice, MercadoPagoPayment, PaymentRecord, PaymentStatus

_DDL = """
CREATE TABLE IF NOT EXISTS payments (
    mp_payment_id   INTEGER PRIMARY KEY,
    status          TEXT    NOT NULL DEFAULT 'fetched',
    transaction_amount REAL NOT NULL,
    date_created    TEXT    NOT NULL,
    cae             TEXT,
    cae_expiry      TEXT,
    invoice_number  INTEGER,
    error_message   TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
)
"""

class PaymentRepository:
    """SQLite-backed store tracking the processing status of MercadoPago payments.

    Status lifecycle:
    ``fetched`` → ``pending_approval`` → ``issued`` | ``rejected``
    ``fetched`` → ``issued`` | ``failed`` (auto approval)
    ``failed`` may retry; ``rejected`` is terminal.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._init_schema()

    def filter_new_payments(
        self, payments: list[MercadoPagoPayment]
    ) -> list[MercadoPagoPayment]:
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
                """SELECT mp_payment_id, status, transaction_amount, date_created,
                          cae, cae_expiry, invoice_number, error_message,
                          created_at, updated_at
                   FROM payments
                   WHERE mp_payment_id = ?""",
                (mp_payment_id,),
            ).fetchone()

        if row is None:
            return None

        return _row_to_payment_record(row)

    def insert_fetched(self, payments: list[MercadoPagoPayment]) -> None:
        """Persist *payments* with status ``fetched``."""
        now = _utcnow()
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
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE payments
                   SET status='issued', cae=?, cae_expiry=?, invoice_number=?, updated_at=?
                   WHERE mp_payment_id=?""",
                (invoice.cae, invoice.cae_expiry, invoice.invoice_number, now, mp_payment_id),
            )

    def mark_failed(self, mp_payment_id: int, error: str) -> None:
        """Transition payment to ``failed`` and store the error description."""
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE payments
                   SET status='failed', error_message=?, updated_at=?
                   WHERE mp_payment_id=?""",
                (error, now, mp_payment_id),
            )

    def mark_postponed(self, mp_payment_id: int, error: str) -> None:
        """Transition payment to ``fetched`` and store an error for retry.

        This allows reprocessing on the next sync without notifying the user
        with an invalid invoice preview.
        """
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE payments
                   SET status='fetched', error_message=?, updated_at=?
                   WHERE mp_payment_id=?""",
                (error, now, mp_payment_id),
            )

    def mark_rejected(self, mp_payment_id: int, reason: str = "Rechazado por usuario") -> None:
        """Transition payment to ``rejected`` (terminal, no retries)."""
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """UPDATE payments
                   SET status='rejected', error_message=?, updated_at=?
                   WHERE mp_payment_id=?""",
                (reason, now, mp_payment_id),
            )

    def _list_payments_by_status(self, status: PaymentStatus) -> list[MercadoPagoPayment]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT mp_payment_id, transaction_amount, date_created
                   FROM payments
                   WHERE status = ?
                   ORDER BY date_created ASC""",
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
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                "UPDATE payments SET status=?, updated_at=? WHERE mp_payment_id=?",
                (status, now, mp_payment_id),
            )

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_DDL)

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


def _row_to_payment_record(row: tuple) -> PaymentRecord:
    return PaymentRecord(
        mp_payment_id=row[0],
        status=row[1],
        transaction_amount=Decimal(str(row[2])),
        date_created=row[3],
        cae=row[4],
        cae_expiry=row[5],
        invoice_number=row[6],
        error_message=row[7],
        created_at=row[8],
        updated_at=row[9],
    )


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
