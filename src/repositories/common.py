"""Shared helpers for payment repository implementations."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from ..domain.models import PaymentRecord

SQLITE_DDL = """
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

POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS payments (
    mp_payment_id   BIGINT PRIMARY KEY,
    status          TEXT    NOT NULL DEFAULT 'fetched',
    transaction_amount NUMERIC NOT NULL,
    date_created    TEXT    NOT NULL,
    cae             TEXT,
    cae_expiry      TEXT,
    invoice_number  INTEGER,
    error_message   TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
)
"""

SELECT_PAYMENT = """
SELECT mp_payment_id, status, transaction_amount, date_created,
       cae, cae_expiry, invoice_number, error_message,
       created_at, updated_at
FROM payments
WHERE mp_payment_id = {placeholder}
"""

SELECT_BY_STATUS = """
SELECT mp_payment_id, transaction_amount, date_created
FROM payments
WHERE status = {placeholder}
ORDER BY date_created ASC
"""

COUNT_STATS = """
SELECT
    COUNT(*) AS total,
    COALESCE(SUM(CASE WHEN status = 'issued' THEN 1 ELSE 0 END), 0) AS billed,
    COALESCE(SUM(CASE WHEN status IN ('fetched', 'pending_approval') THEN 1 ELSE 0 END), 0) AS pending
FROM payments
"""


def row_to_payment_record(row: tuple) -> PaymentRecord:
    """Map a database row to a ``PaymentRecord``."""
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


def utcnow() -> str:
    """Return the current UTC timestamp as an ISO string."""
    return datetime.now(timezone.utc).isoformat()
