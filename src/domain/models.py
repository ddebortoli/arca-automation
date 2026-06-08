from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_validator

from .datetime_utils import to_art


class MercadoPagoPayment(BaseModel):
    """Represents a single transfer fetched from the MercadoPago Payments API."""

    id: int
    date_created: datetime
    transaction_amount: Decimal
    status: str

    @field_validator("date_created", mode="before")
    @classmethod
    def normalize_date_created(cls, value: datetime | str) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return to_art(value)


class IssuedInvoice(BaseModel):
    """Result returned by AFIP after a voucher is successfully created."""

    cae: str
    cae_expiry: str
    invoice_number: int


class InvoicePreview(BaseModel):
    """Human-readable summary of a voucher about to be issued."""

    payment_id: int
    amount: Decimal
    service_date: datetime
    invoice_type: str
    point_of_sale: int
    next_invoice_number: int
    receiver: str
    concept: str

    @property
    def formatted_voucher(self) -> str:
        return (
            f"{self.invoice_type} "
            f"{self.point_of_sale:05d}-{self.next_invoice_number:08d}"
        )


PaymentStatus = Literal[
    "fetched",
    "pending_approval",
    "issued",
    "failed",
    "rejected",
]


class PaymentRecord(BaseModel):
    """Persistent representation of a payment stored in the local database."""

    mp_payment_id: int
    status: PaymentStatus
    transaction_amount: Decimal
    date_created: datetime
    cae: str | None = None
    cae_expiry: str | None = None
    invoice_number: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
