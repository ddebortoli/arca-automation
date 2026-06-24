from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.domain.exceptions import InvalidPaymentStateError, PaymentNotFoundError
from src.domain.models import InvoicePreview, IssuedInvoice, MercadoPagoPayment
from src.repositories.sqlite_payment_repository import SqlitePaymentRepository
from src.use_cases.issue_invoice import IssueInvoiceUseCase
from src.use_cases.process_payments import ProcessPaymentsUseCase
from src.use_cases.postpone_payment import PostponePaymentUseCase
from src.use_cases.reject_payment import RejectPaymentUseCase

_ART = ZoneInfo("America/Argentina/Buenos_Aires")


def _payment(payment_id: int, amount: str = "100.00") -> MercadoPagoPayment:
    return MercadoPagoPayment(
        id=payment_id,
        transaction_amount=Decimal(amount),
        date_created=datetime(2026, 6, 5, 12, 0, tzinfo=_ART),
        status="fetched",
    )


def _preview(payment_id: int) -> InvoicePreview:
    return InvoicePreview(
        payment_id=payment_id,
        amount=Decimal("100.00"),
        service_date=datetime(2026, 6, 5, 12, 0, tzinfo=_ART),
        invoice_type="Factura C",
        point_of_sale=2,
        next_invoice_number=10,
        receiver="Consumidor Final",
        concept="Servicios",
    )


@pytest.fixture
def repository(tmp_path) -> SqlitePaymentRepository:
    return SqlitePaymentRepository(tmp_path / "payments.db")


@pytest.fixture
def afip_provider() -> MagicMock:
    provider = MagicMock()
    provider.build_invoice_preview.side_effect = lambda payment: _preview(payment.id)
    provider.issue_invoice.return_value = IssuedInvoice(
        cae="123",
        cae_expiry="20260614",
        invoice_number=10,
    )
    return provider


def test_process_payments_auto_mode_issues_fetched(
    repository: SqlitePaymentRepository,
    afip_provider: MagicMock,
) -> None:
    approval = MagicMock()
    approval.requires_manual_approval.return_value = False

    mp = MagicMock()
    mp.fetch_transfers.return_value = [_payment(1)]

    use_case = ProcessPaymentsUseCase(mp, afip_provider, approval, repository)
    use_case.execute()

    payment = repository.get_payment(1)
    assert payment is not None
    assert payment.status == "issued"
    approval.submit_for_approval.assert_not_called()


def test_process_payments_telegram_mode_marks_pending(
    repository: SqlitePaymentRepository,
    afip_provider: MagicMock,
) -> None:
    approval = MagicMock()
    approval.requires_manual_approval.return_value = True

    mp = MagicMock()
    mp.fetch_transfers.return_value = [_payment(2)]

    use_case = ProcessPaymentsUseCase(mp, afip_provider, approval, repository)
    use_case.execute()

    payment = repository.get_payment(2)
    assert payment is not None
    assert payment.status == "pending_approval"
    afip_provider.issue_invoice.assert_not_called()
    approval.submit_for_approval.assert_called_once()


def test_issue_invoice_from_approval(
    repository: SqlitePaymentRepository, afip_provider: MagicMock
) -> None:
    repository.insert_fetched([_payment(3)])
    repository.mark_pending_approval(3)

    invoice = IssueInvoiceUseCase(afip_provider, repository).execute(3, from_approval=True)

    payment = repository.get_payment(3)
    assert payment is not None
    assert payment.status == "issued"
    assert invoice.cae == "123"


def test_issue_invoice_rejects_wrong_status(
    repository: SqlitePaymentRepository,
    afip_provider: MagicMock,
) -> None:
    repository.insert_fetched([_payment(4)])

    with pytest.raises(InvalidPaymentStateError):
        IssueInvoiceUseCase(afip_provider, repository).execute(4, from_approval=True)


def test_reject_payment_is_terminal(repository: SqlitePaymentRepository) -> None:
    repository.insert_fetched([_payment(5)])
    repository.mark_pending_approval(5)

    RejectPaymentUseCase(repository).execute(5)

    payment = repository.get_payment(5)
    assert payment is not None
    assert payment.status == "rejected"


def test_reject_payment_not_found(repository: SqlitePaymentRepository) -> None:
    with pytest.raises(PaymentNotFoundError):
        RejectPaymentUseCase(repository).execute(999)


def test_postpone_payment_returns_to_fetched(
    repository: SqlitePaymentRepository,
) -> None:
    repository.insert_fetched([_payment(6)])
    repository.mark_pending_approval(6)

    PostponePaymentUseCase(repository).execute(6)

    payment = repository.get_payment(6)
    assert payment is not None
    assert payment.status == "fetched"
    assert repository.list_fetched()[0].id == 6


def test_postpone_then_resubmit_on_next_sync(
    repository: SqlitePaymentRepository,
    afip_provider: MagicMock,
) -> None:
    approval = MagicMock()
    approval.requires_manual_approval.return_value = True
    mp = MagicMock()
    mp.fetch_transfers.return_value = []

    repository.insert_fetched([_payment(7)])
    repository.mark_pending_approval(7)
    PostponePaymentUseCase(repository).execute(7)

    ProcessPaymentsUseCase(mp, afip_provider, approval, repository).execute()

    payment = repository.get_payment(7)
    assert payment is not None
    assert payment.status == "pending_approval"
    approval.submit_for_approval.assert_called_once()
