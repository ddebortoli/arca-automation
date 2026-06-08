from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import httpx
import pytest

from src.domain.config import ApprovalConfig
from src.domain.exceptions import ApprovalError
from src.domain.models import InvoicePreview, MercadoPagoPayment
from src.providers.approval.telegram import (
    TelegramApprovalProvider,
    _format_message,
    format_postponed_message,
)

_ART = ZoneInfo("America/Argentina/Buenos_Aires")


def _config() -> ApprovalConfig:
    return ApprovalConfig(
        mode="telegram",
        telegram_bot_token="token",
        telegram_chat_id="12345",
    )


def test_format_message_includes_voucher_details() -> None:
    preview = InvoicePreview(
        payment_id=42,
        amount=Decimal("701503.20"),
        service_date=datetime(2026, 6, 5, 18, 44, 17, tzinfo=_ART),
        invoice_type="Factura C",
        point_of_sale=2,
        next_invoice_number=4,
        receiver="Consumidor Final",
        concept="Servicios",
    )

    message = _format_message(preview)

    assert "Pago MP: #42" in message
    assert "701.503,20" in message
    assert "Factura C 00002-00000004" in message
    assert "Consumidor Final" in message


def test_format_postponed_message_includes_invoice_details() -> None:
    preview = InvoicePreview(
        payment_id=42,
        amount=Decimal("701503.20"),
        service_date=datetime(2026, 6, 5, 18, 44, 17, tzinfo=_ART),
        invoice_type="Factura C",
        point_of_sale=2,
        next_invoice_number=4,
        receiver="Consumidor Final",
        concept="Servicios",
    )

    message = format_postponed_message(preview)

    assert "⏸ Factura pospuesta" in message
    assert "Pago MP: #42" in message
    assert "Factura C 00002-00000004" in message
    assert "próximo sync" in message


def test_submit_for_approval_sends_inline_keyboard() -> None:
    provider = TelegramApprovalProvider(_config())
    payment = MercadoPagoPayment(
        id=99,
        transaction_amount=Decimal("10"),
        date_created=datetime(2026, 6, 5, tzinfo=_ART),
        status="fetched",
    )
    preview = InvoicePreview(
        payment_id=99,
        amount=Decimal("10"),
        service_date=datetime(2026, 6, 5, tzinfo=_ART),
        invoice_type="Factura C",
        point_of_sale=2,
        next_invoice_number=1,
        receiver="Consumidor Final",
        concept="Servicios",
    )

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"ok": True}

    with patch("src.providers.approval.telegram.httpx.post", return_value=response) as post:
        provider.submit_for_approval(payment, preview)

    payload = post.call_args.kwargs["json"]
    assert payload["chat_id"] == "12345"
    assert payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "approve:99"
    assert payload["reply_markup"]["inline_keyboard"][0][1]["callback_data"] == "reject:99"
    assert payload["reply_markup"]["inline_keyboard"][1][0]["callback_data"] == "postpone:99"


def test_submit_for_approval_raises_on_http_error() -> None:
    provider = TelegramApprovalProvider(_config())
    payment = MercadoPagoPayment(
        id=1,
        transaction_amount=Decimal("10"),
        date_created=datetime(2026, 6, 5, tzinfo=_ART),
        status="fetched",
    )
    preview = InvoicePreview(
        payment_id=1,
        amount=Decimal("10"),
        service_date=datetime(2026, 6, 5, tzinfo=_ART),
        invoice_type="Factura C",
        point_of_sale=2,
        next_invoice_number=1,
        receiver="Consumidor Final",
        concept="Servicios",
    )

    with patch(
        "src.providers.approval.telegram.httpx.post",
        side_effect=httpx.HTTPError("network"),
    ):
        with pytest.raises(ApprovalError):
            provider.submit_for_approval(payment, preview)
