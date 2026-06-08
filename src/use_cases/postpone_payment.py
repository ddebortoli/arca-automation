import logging

from ..domain.exceptions import InvalidPaymentStateError, PaymentNotFoundError
from ..repositories.payment_repository import PaymentRepository

logger = logging.getLogger(__name__)


class PostponePaymentUseCase:
    """Return a pending payment to ``fetched`` for a later approval cycle."""

    def __init__(self, repository: PaymentRepository) -> None:
        self._repo = repository

    def execute(self, payment_id: int) -> None:
        """Postpone *payment_id* so it can be reviewed again on the next sync.

        Raises:
            PaymentNotFoundError: If the payment does not exist.
            InvalidPaymentStateError: If the payment is not ``pending_approval``.
        """
        payment = self._repo.get_payment(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment {payment_id} not found")

        if payment.status != "pending_approval":
            raise InvalidPaymentStateError(
                f"Payment {payment_id} cannot be postponed from status '{payment.status}'"
            )

        self._repo.mark_fetched(payment_id)
        logger.info("Payment %d postponed — will be offered again on next sync", payment_id)
