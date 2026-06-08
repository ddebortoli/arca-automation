import logging

from ..domain.exceptions import AfipInvoiceError, InvalidPaymentStateError, PaymentNotFoundError
from ..domain.models import IssuedInvoice, PaymentStatus
from ..domain.ports import AfipPort
from ..repositories.payment_repository import PaymentRepository

logger = logging.getLogger(__name__)

_ALLOWED_STATUSES: dict[bool, frozenset[PaymentStatus]] = {
    False: frozenset({"fetched"}),
    True: frozenset({"pending_approval"}),
}


class IssueInvoiceUseCase:
    """Issue a single AFIP voucher for an approved or auto-mode payment."""

    def __init__(
        self,
        afip_provider: AfipPort,
        repository: PaymentRepository,
    ) -> None:
        self._afip = afip_provider
        self._repo = repository

    def execute(self, payment_id: int, *, from_approval: bool = False) -> IssuedInvoice:
        """Create the AFIP voucher for *payment_id*.

        Args:
            payment_id: MercadoPago payment identifier.
            from_approval: When True, only ``pending_approval`` payments are accepted.

        Raises:
            PaymentNotFoundError: If the payment does not exist.
            InvalidPaymentStateError: If the payment is not in an issuable status.
            AfipInvoiceError: If AFIP rejects or fails to process the request.
        """
        payment = self._repo.get_payment(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment {payment_id} not found")

        allowed = _ALLOWED_STATUSES[from_approval]
        if payment.status not in allowed:
            raise InvalidPaymentStateError(
                f"Payment {payment_id} cannot be issued from status '{payment.status}'"
            )

        logger.info(
            "Issuing invoice for payment %d — amount: %s ARS",
            payment_id,
            payment.transaction_amount,
        )

        try:
            invoice = self._afip.issue_invoice(
                payment.transaction_amount,
                payment.date_created,
            )
            self._repo.mark_issued(payment_id, invoice)
            logger.info(
                "Payment %d → CAE %s (invoice #%d, expires %s)",
                payment_id,
                invoice.cae,
                invoice.invoice_number,
                invoice.cae_expiry,
            )
            return invoice
        except AfipInvoiceError as exc:
            logger.error("Payment %d — AFIP error: %s", payment_id, exc)
            self._repo.mark_failed(payment_id, str(exc))
            raise
