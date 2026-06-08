import logging

from ..domain.exceptions import InvalidPaymentStateError, PaymentNotFoundError
from ..repositories.payment_repository import PaymentRepository

logger = logging.getLogger(__name__)


class RejectPaymentUseCase:
    """Mark a pending payment as permanently rejected."""

    def __init__(self, repository: PaymentRepository) -> None:
        self._repo = repository

    def execute(self, payment_id: int, reason: str = "Rechazado por usuario") -> None:
        """Reject *payment_id* without issuing an AFIP voucher.

        Raises:
            PaymentNotFoundError: If the payment does not exist.
            InvalidPaymentStateError: If the payment is not ``pending_approval``.
        """
        payment = self._repo.get_payment(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment {payment_id} not found")

        if payment.status != "pending_approval":
            raise InvalidPaymentStateError(
                f"Payment {payment_id} cannot be rejected from status '{payment.status}'"
            )

        self._repo.mark_rejected(payment_id, reason)
        logger.info("Payment %d rejected — %s", payment_id, reason)
