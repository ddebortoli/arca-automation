from datetime import datetime
from decimal import Decimal
from typing import Protocol

from .models import InvoicePreview, IssuedInvoice, MercadoPagoPayment


class MercadoPagoPort(Protocol):
    """Contract for fetching income payments from MercadoPago."""

    def fetch_transfers(self, begin_date: str, end_date: str) -> list[MercadoPagoPayment]:
        """Return all income payments within the given date range.

        Income is defined as payments where the authenticated user is the collector.

        Args:
            begin_date: MP relative formula (inclusive lower bound), e.g. ``"NOW-17DAYS"``.
            end_date: MP relative formula (inclusive upper bound), e.g. ``"NOW"``.

        Returns:
            List of payments ordered by date descending.
        """
        ...


class AfipPort(Protocol):
    """Contract for issuing electronic invoices through AFIP."""

    def build_invoice_preview(self, payment: MercadoPagoPayment) -> InvoicePreview:
        """Return a preview of the voucher that would be issued for *payment*."""
        ...

    def issue_invoice(self, amount: Decimal, date: datetime) -> IssuedInvoice:
        """Create a Factura C for *amount* pesos on *date*.

        Args:
            amount: Total amount in ARS (maps 1:1 to ImpTotal and ImpNeto).
            date: The service date used for FchServDesde/Hasta and FchVtoPago.

        Returns:
            The issued invoice with its CAE and voucher number.

        Raises:
            AfipInvoiceError: If AFIP rejects or fails to process the request.
        """
        ...


class ApprovalPort(Protocol):
    """Contract for optional human approval before AFIP emission."""

    def requires_manual_approval(self) -> bool:
        """Return whether invoices must be confirmed by a human."""
        ...

    def submit_for_approval(
        self,
        payment: MercadoPagoPayment,
        preview: InvoicePreview,
    ) -> None:
        """Notify an approver and wait for an external decision.

        Raises:
            ApprovalError: If the approval request cannot be delivered.
        """
        ...

    def notify_afip_validation(
        self,
        payment: MercadoPagoPayment,
        *,
        errors: list[str],
        events: list[str],
    ) -> None:
        """Send AFIP validation warnings/errors to the user (if applicable).

        This is used to avoid sending an incorrect approval request when AFIP
        reports credential/service issues; for non-interactive modes it is a
        no-op.
        """
        ...
