from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from src.domain.exceptions import AfipInvoiceError
from src.domain.models import MercadoPagoPayment
from src.repositories.payment_repository import PaymentRepository
from src.use_cases.process_payments import ProcessPaymentsUseCase


class _FakeApproval:
    def requires_manual_approval(self) -> bool:
        return True

    def submit_for_approval(self, payment: MercadoPagoPayment, preview: object) -> None:
        raise AssertionError("Should not submit approval when AFIP errors")

    def notify_afip_validation(
        self,
        payment: MercadoPagoPayment,
        *,
        errors: list[str],
        events: list[str],
    ) -> None:
        # Test only ensures we skip approval and mark the payment for retry.
        return


class _FakeMp:
    def fetch_transfers(self, begin_date: str, end_date: str) -> list[MercadoPagoPayment]:
        return [
            MercadoPagoPayment(
                id=1,
                date_created=datetime.now(),
                transaction_amount=Decimal("10.0"),
                status="paid",
            )
        ]


class _FakeAfip:
    def __init__(self) -> None:
        self._called = False

    def build_invoice_preview(self, payment: MercadoPagoPayment) -> object:
        self._called = True
        raise AfipInvoiceError("AFIP rejected")

    def issue_invoice(self, amount: Decimal, date: datetime) -> object:
        raise AssertionError("Not used in manual approval mode")


def test_afip_errors_skip_approval_and_mark_failed(tmp_path) -> None:
    repo = PaymentRepository(db_path=tmp_path / "payments.db")
    use_case = ProcessPaymentsUseCase(
        mp_provider=_FakeMp(),
        afip_provider=_FakeAfip(),
        approval_provider=_FakeApproval(),
        repository=repo,
    )

    use_case.execute()

    payment = repo.get_payment(1)
    assert payment is not None
    assert payment.status == "fetched"
