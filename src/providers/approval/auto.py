from ...domain.models import InvoicePreview, MercadoPagoPayment


class AutoApprovalProvider:
    """Skips manual approval and lets the sync pipeline issue immediately."""

    def requires_manual_approval(self) -> bool:
        return False

    def submit_for_approval(
        self,
        payment: MercadoPagoPayment,
        preview: InvoicePreview,
    ) -> None:
        raise RuntimeError("AutoApprovalProvider does not submit for approval")
