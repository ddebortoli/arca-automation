"""Payment repository public API.

``PaymentRepository`` is kept as an alias for the SQLite implementation so
existing imports and tests continue to work.
"""

from .sqlite_payment_repository import SqlitePaymentRepository

PaymentRepository = SqlitePaymentRepository

__all__ = ["PaymentRepository", "SqlitePaymentRepository"]
