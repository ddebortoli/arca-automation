import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from ..domain.exceptions import AfipInvoiceError, AfipValidationError, ApprovalError
from ..domain.models import MercadoPagoPayment
from ..domain.ports import AfipPort, ApprovalPort, MercadoPagoPort
from ..domain.ports import PaymentRepositoryPort
from .issue_invoice import IssueInvoiceUseCase

logger = logging.getLogger(__name__)

_ART_TZ = ZoneInfo("America/Argentina/Buenos_Aires")


class ProcessPaymentsUseCase:
    """Orchestrates the MercadoPago fetch and optional approval pipeline.

    For each run:
    1. Compute the current-month date range in ART timezone.
    2. Fetch transfers from MercadoPago.
    3. Persist unseen payments as ``fetched``.
    4. Auto mode: issue AFIP vouchers for ``fetched`` payments.
    5. Telegram mode: send approval requests and move to ``pending_approval``.
    """

    def __init__(
        self,
        mp_provider: MercadoPagoPort,
        afip_provider: AfipPort,
        approval_provider: ApprovalPort,
        repository: PaymentRepositoryPort,
    ) -> None:
        self._mp = mp_provider
        self._afip = afip_provider
        self._approval = approval_provider
        self._repo = repository
        self._issue_invoice = IssueInvoiceUseCase(afip_provider, repository)

    def execute(self) -> None:
        """Run the sync pipeline. Safe to call multiple times (idempotent)."""
        begin_date, end_date = _current_month_range()
        logger.info("Processing payments from %s to %s", begin_date, end_date)

        payments = self._mp.fetch_transfers(begin_date, end_date)
        logger.info("MercadoPago returned %d transfer(s)", len(payments))

        new_payments = self._repo.filter_new_payments(payments)
        if new_payments:
            logger.info("%d new payment(s) to record", len(new_payments))
            self._repo.insert_fetched(new_payments)

        pending = self._repo.list_fetched()
        logger.info("%d payment(s) ready for processing", len(pending))

        if not pending:
            logger.info("Nothing to do — no payments awaiting processing")
            return

        if self._approval.requires_manual_approval():
            self._submit_for_approval(pending)
            return

        self._issue_automatically(pending)

    def _submit_for_approval(self, payments: list[MercadoPagoPayment]) -> None:
        submitted = 0
        for payment in payments:
            validation_errors: list[str] = []
            validation_events: list[str] = []

            validate_fn = getattr(self._afip, "validate_configuration", None)
            if callable(validate_fn):
                try:
                    result = validate_fn()
                    if isinstance(result, tuple) and len(result) == 2:
                        validation_errors, validation_events = result
                    else:
                        validation_errors, validation_events = [], []
                except AfipValidationError as exc:
                    validation_errors = [str(exc)]
                    self._repo.mark_postponed(payment.id, str(exc))
                    logger.error(
                        "Payment %d — AFIP validation failed, posponiendo: %s",
                        payment.id,
                        exc,
                    )
                    self._approval.notify_afip_validation(
                        payment,
                        errors=validation_errors,
                        events=[],
                    )
                    continue

            try:
                preview = self._afip.build_invoice_preview(payment)
            except AfipInvoiceError as exc:
                validation_errors = [str(exc)]
                self._repo.mark_postponed(payment.id, str(exc))
                logger.error(
                    "Payment %d — AFIP WSFE validation failed, posponiendo: %s",
                    payment.id,
                    exc,
                )
                self._approval.notify_afip_validation(
                    payment,
                    errors=validation_errors,
                    events=[],
                )
                continue

            try:
                if validation_events:
                    # Notify AFIP warnings before asking the user.
                    try:
                        self._approval.notify_afip_validation(
                            payment,
                            errors=[],
                            events=validation_events,
                        )
                    except ApprovalError as exc:
                        logger.error(
                            "Payment %d — Telegram AFIP warning notice failed: %s",
                            payment.id,
                            exc,
                        )
                self._approval.submit_for_approval(payment, preview)
            except ApprovalError as exc:
                logger.error(
                    "Payment %d — approval notification failed: %s",
                    payment.id,
                    exc,
                )
                continue

            self._repo.mark_pending_approval(payment.id)
            submitted += 1
            logger.info("Payment %d sent for manual approval", payment.id)

        logger.info("Run complete — pending approval: %d", submitted)

    def _issue_automatically(self, payments: list[MercadoPagoPayment]) -> None:
        issued = 0
        failed = 0
        for payment in payments:
            try:
                self._issue_invoice.execute(payment.id, from_approval=False)
                issued += 1
            except Exception:
                failed += 1

        logger.info("Run complete — issued: %d, failed: %d", issued, failed)


def _current_month_range() -> tuple[str, str]:
    """Return (begin_date, end_date) in MercadoPago's relative formula format."""
    now = datetime.now(_ART_TZ)
    days_since_first = now.day - 1
    begin_date = f"NOW-{days_since_first}DAYS" if days_since_first > 0 else "NOW"
    return begin_date, "NOW"
