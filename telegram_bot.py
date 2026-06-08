"""Telegram bot worker for manual invoice approval.

Run as a long-lived process alongside the cron sync job:
    uv run telegram_bot.py
"""
import logging
import sys
import time
from pathlib import Path

import httpx

from src.bootstrap import (
    build_afip_provider,
    build_issue_invoice_use_case,
    build_postpone_payment_use_case,
    build_reject_payment_use_case,
    build_repository,
    load_approval_config,
    load_runtime_config,
)
from src.domain.config import ApprovalConfig
from src.domain.exceptions import (
    AfipInvoiceError,
    ApprovalError,
    InvalidPaymentStateError,
    PaymentNotFoundError,
)
from src.domain.models import MercadoPagoPayment
from src.domain.ports import AfipPort
from src.providers.approval.telegram import (
    TelegramApprovalProvider,
    format_postponed_message,
)
from src.repositories.payment_repository import PaymentRepository

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
_DB_PATH = Path(__file__).parent / "payments.db"
_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
_POLL_TIMEOUT_SECONDS = 30


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=_LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


class TelegramApprovalBot:
    """Polls Telegram for approval callbacks and triggers AFIP emission."""

    def __init__(
        self,
        approval_config: ApprovalConfig,
        telegram: TelegramApprovalProvider,
        afip_provider: AfipPort,
        repository: PaymentRepository,
        issue_invoice,
        reject_payment,
        postpone_payment,
    ) -> None:
        self._chat_id = str(approval_config.telegram_chat_id)
        self._bot_token = approval_config.telegram_bot_token
        self._telegram = telegram
        self._afip = afip_provider
        self._repository = repository
        self._issue_invoice = issue_invoice
        self._reject_payment = reject_payment
        self._postpone_payment = postpone_payment
        self._offset = 0

    def run(self) -> None:
        logger = logging.getLogger(__name__)
        logger.info("Telegram approval bot started — waiting for callbacks")

        while True:
            updates = self._poll_updates()
            for update in updates:
                self._offset = update["update_id"] + 1
                try:
                    self._handle_update(update)
                except Exception:
                    logger.exception("Unhandled error processing Telegram update")

    def _poll_updates(self) -> list[dict]:
        response = httpx.get(
            _TELEGRAM_API.format(token=self._bot_token, method="getUpdates"),
            params={"offset": self._offset, "timeout": _POLL_TIMEOUT_SECONDS},
            timeout=_POLL_TIMEOUT_SECONDS + 10,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram getUpdates failed: {data}")
        return data.get("result", [])

    def _handle_update(self, update: dict) -> None:
        callback = update.get("callback_query")
        if callback is None:
            return

        logger = logging.getLogger(__name__)
        chat_id = str(callback["message"]["chat"]["id"])
        if chat_id != self._chat_id:
            logger.warning("Ignoring callback from chat %s", chat_id)
            return

        action, payment_id = _parse_callback_data(callback["data"])
        message_id = callback["message"]["message_id"]
        callback_id = callback["id"]
        logger.info("Callback received: %s for payment %d", action, payment_id)

        if action == "approve":
            self._handle_approve(payment_id, callback_id, message_id, chat_id)
            return

        if action == "reject":
            self._handle_reject(payment_id, callback_id, message_id, chat_id)
            return

        if action == "postpone":
            self._handle_postpone(payment_id, callback_id, message_id, chat_id)
            return

        logger.warning("Unknown callback action: %s", action)
        self._telegram.answer_callback(callback_id, "Acción no reconocida")

    def _handle_approve(
        self,
        payment_id: int,
        callback_id: str,
        message_id: int,
        chat_id: str,
    ) -> None:
        logger = logging.getLogger(__name__)
        self._telegram.answer_callback(callback_id, "Emitiendo factura...")
        try:
            invoice = self._issue_invoice.execute(payment_id, from_approval=True)
            self._telegram.edit_message(
                int(chat_id),
                message_id,
                (
                    f"✅ Factura emitida — pago #{payment_id}\n"
                    f"CAE: {invoice.cae}\n"
                    f"Comprobante #: {invoice.invoice_number}\n"
                    f"Vence: {invoice.cae_expiry}"
                ),
            )
        except PaymentNotFoundError:
            self._telegram.answer_callback(callback_id, "Pago no encontrado")
        except InvalidPaymentStateError as exc:
            self._telegram.answer_callback(callback_id, str(exc))
        except AfipInvoiceError as exc:
            self._telegram.edit_message(
                int(chat_id),
                message_id,
                f"⚠️ AFIP rechazó el pago #{payment_id}\n{exc}",
            )
            logger.error("AFIP error on payment %d: %s", payment_id, exc)
        except ApprovalError as exc:
            logger.error("Telegram API error on approve for %d: %s", payment_id, exc)

    def _handle_reject(
        self,
        payment_id: int,
        callback_id: str,
        message_id: int,
        chat_id: str,
    ) -> None:
        self._telegram.answer_callback(callback_id, "Rechazando...")
        try:
            self._reject_payment.execute(payment_id)
            self._telegram.edit_message(
                int(chat_id),
                message_id,
                f"❌ Pago #{payment_id} rechazado — no se facturará",
            )
        except PaymentNotFoundError:
            self._telegram.answer_callback(callback_id, "Pago no encontrado")
        except InvalidPaymentStateError as exc:
            self._telegram.answer_callback(callback_id, str(exc))
        except ApprovalError as exc:
            logging.getLogger(__name__).error(
                "Telegram API error on reject for %d: %s", payment_id, exc
            )

    def _handle_postpone(
        self,
        payment_id: int,
        callback_id: str,
        message_id: int,
        chat_id: str,
    ) -> None:
        logger = logging.getLogger(__name__)
        self._telegram.answer_callback(callback_id, "Posponiendo...")
        try:
            preview = self._build_preview_for_payment(payment_id)
            self._postpone_payment.execute(payment_id)
            self._telegram.edit_message(
                int(chat_id),
                message_id,
                format_postponed_message(preview),
            )
            logger.info("Payment %d postponed successfully", payment_id)
        except PaymentNotFoundError:
            self._telegram.answer_callback(callback_id, "Pago no encontrado")
        except InvalidPaymentStateError as exc:
            self._telegram.answer_callback(callback_id, str(exc))
            logger.warning("Cannot postpone payment %d: %s", payment_id, exc)
        except ApprovalError as exc:
            logger.error("Telegram API error on postpone for %d: %s", payment_id, exc)
            self._telegram.answer_callback(callback_id, "No se pudo actualizar el mensaje")

    def _build_preview_for_payment(self, payment_id: int):
        payment = self._repository.get_payment(payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment {payment_id} not found")

        mp_payment = MercadoPagoPayment(
            id=payment.mp_payment_id,
            transaction_amount=payment.transaction_amount,
            date_created=payment.date_created,
            status=payment.status,
        )
        return self._afip.build_invoice_preview(mp_payment)


def _parse_callback_data(data: str) -> tuple[str, int]:
    action, payment_id = data.split(":", maxsplit=1)
    return action, int(payment_id)


def main() -> None:
    _configure_logging()
    logger = logging.getLogger(__name__)

    try:
        config = load_runtime_config()
        approval_config = load_approval_config()
    except (EnvironmentError, ValueError) as exc:
        logging.critical(str(exc))
        sys.exit(1)

    if approval_config.mode != "telegram":
        logging.critical("telegram_bot.py requires APPROVAL_MODE=telegram")
        sys.exit(1)

    repository = build_repository(_DB_PATH)
    afip_provider = build_afip_provider(config)
    telegram = TelegramApprovalProvider(approval_config)

    bot = TelegramApprovalBot(
        approval_config=approval_config,
        telegram=telegram,
        afip_provider=afip_provider,
        repository=repository,
        issue_invoice=build_issue_invoice_use_case(afip_provider, repository),
        reject_payment=build_reject_payment_use_case(repository),
        postpone_payment=build_postpone_payment_use_case(repository),
    )

    while True:
        try:
            bot.run()
        except KeyboardInterrupt:
            logger.info("Telegram bot stopped")
            break
        except httpx.HTTPError as exc:
            logger.error("Telegram polling error: %s — retrying in 5s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
