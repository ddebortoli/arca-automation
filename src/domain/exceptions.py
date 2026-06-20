class MercadoPagoError(Exception):
    """Raised when the MercadoPago API returns an unexpected response."""


class AfipInvoiceError(Exception):
    """Raised when AFIP fails to create a voucher for a given payment."""


class AfipValidationError(Exception):
    """Raised when AFIP endpoints report credential/service configuration issues."""


class PaymentNotFoundError(Exception):
    """Raised when a payment ID does not exist in the repository."""


class InvalidPaymentStateError(Exception):
    """Raised when a payment transition is not allowed for its current status."""


class ApprovalError(Exception):
    """Raised when an approval notification cannot be delivered."""
