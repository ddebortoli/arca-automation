import logging

import httpx

from ...domain.config import ApprovalConfig
from ...domain.exceptions import ApprovalError
from ...domain.models import InvoicePreview, MercadoPagoPayment

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramApprovalProvider:
    """Sends invoice previews to Telegram and waits for inline-button decisions."""

    def __init__(self, config: ApprovalConfig) -> None:
        self._bot_token = config.telegram_bot_token
        self._chat_id = config.telegram_chat_id

    def requires_manual_approval(self) -> bool:
        return True

    def submit_for_approval(
        self,
        payment: MercadoPagoPayment,
        preview: InvoicePreview,
    ) -> None:
        message = _format_message(preview)
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Confirmar",
                        "callback_data": f"approve:{payment.id}",
                    },
                    {
                        "text": "❌ Rechazar",
                        "callback_data": f"reject:{payment.id}",
                    },
                ],
                [
                    {
                        "text": "⏸ Posponer",
                        "callback_data": f"postpone:{payment.id}",
                    },
                ],
            ]
        }

        try:
            self._api_post(
                "sendMessage",
                {
                    "chat_id": self._chat_id,
                    "text": message,
                    "reply_markup": keyboard,
                },
            )
        except httpx.HTTPError as exc:
            raise ApprovalError(
                f"Failed to send Telegram approval for payment {payment.id}: {exc}"
            ) from exc

        logger.info("Approval request sent to Telegram for payment %d", payment.id)

    def answer_callback(self, callback_query_id: str, text: str) -> None:
        """Acknowledge a button press in Telegram."""
        self._api_post(
            "answerCallbackQuery",
            {"callback_query_id": callback_query_id, "text": text},
        )

    def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        """Replace the original approval message and remove inline buttons."""
        self._api_post(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": {"inline_keyboard": []},
            },
        )

    def _api_post(self, method: str, payload: dict) -> dict:
        url = _TELEGRAM_API.format(token=self._bot_token, method=method)
        response = httpx.post(url, json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise ApprovalError(f"Telegram API error on {method}: {data}")
        return data


def _format_amount(amount) -> str:
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_invoice_details(preview: InvoicePreview) -> str:
    """Return the invoice fields shared by approval and outcome messages."""
    service_date = preview.service_date.strftime("%d/%m/%Y")
    amount = _format_amount(preview.amount)
    return (
        f"Pago MP: #{preview.payment_id}\n"
        f"Monto: ${amount} ARS\n"
        f"Fecha servicio: {service_date}\n"
        f"Comprobante: {preview.formatted_voucher}\n"
        f"Receptor: {preview.receiver}\n"
        f"Concepto: {preview.concept}"
    )


def _format_message(preview: InvoicePreview) -> str:
    return f"Facturar este pago?\n\n{format_invoice_details(preview)}"


def format_postponed_message(preview: InvoicePreview) -> str:
    """Build the confirmation shown after a payment is postponed."""
    return (
        "⏸ Factura pospuesta\n\n"
        f"{format_invoice_details(preview)}\n\n"
        "Se volverá a ofrecer en el próximo sync."
    )
