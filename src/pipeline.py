"""Shared entry points for running the payment pipeline and Telegram bot."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass

from .bootstrap import (
    build_afip_provider,
    build_issue_invoice_use_case,
    build_mercadopago_provider,
    build_postpone_payment_use_case,
    build_process_payments_use_case,
    build_reject_payment_use_case,
    build_repository,
    configure_observability,
    load_approval_config,
    load_runtime_config,
)
from .domain.config import ApprovalConfig
from .domain.exceptions import AfipValidationError
from .domain.ports import PaymentRepositoryPort
from .providers.approval import build_approval_provider
from .providers.approval.telegram import TelegramApprovalProvider
from .providers.approval.telegram_bot_worker import TelegramApprovalBot

logger = logging.getLogger(__name__)

_telegram_bot_thread: threading.Thread | None = None
_telegram_bot_lock = threading.Lock()


@dataclass(frozen=True)
class TelegramBotStartResult:
    """Outcome of attempting to start the Telegram approval bot thread."""

    thread: threading.Thread | None
    reused_existing: bool


def run_payment_pipeline(*, validate_afip: bool | None = None) -> None:
    """Bootstrap dependencies and execute the payment processing pipeline."""
    configure_observability()

    config = load_runtime_config()
    approval_config = load_approval_config()
    repository = build_repository()
    afip_provider = build_afip_provider(config)

    should_validate = (
        validate_afip if validate_afip is not None else os.getenv("AFIP_VALIDATE_CERT") == "1"
    )
    if should_validate:
        afip_provider.validate_configuration()
        logger.info("AFIP certificate/config validation: OK")

    use_case = build_process_payments_use_case(
        mp_provider=build_mercadopago_provider(config),
        afip_provider=afip_provider,
        approval_provider=build_approval_provider(approval_config),
        repository=repository,
    )

    logger.info(
        "Starting payment processing run (approval_mode=%s)",
        approval_config.mode,
    )
    use_case.execute()
    logger.info("Run finished")


def run_payment_pipeline_safe(*, validate_afip: bool | None = None) -> None:
    """Run the pipeline, translating configuration errors into log messages."""
    try:
        run_payment_pipeline(validate_afip=validate_afip)
    except AfipValidationError as exc:
        logger.critical("AFIP certificate/config validation: FAILED: %s", exc)
        raise
    except (EnvironmentError, ValueError) as exc:
        logger.critical(str(exc))
        raise


def create_telegram_bot(
    *,
    config: dict[str, str] | None = None,
    approval_config: ApprovalConfig | None = None,
    repository: PaymentRepositoryPort | None = None,
) -> TelegramApprovalBot:
    """Build a configured Telegram approval bot instance."""
    runtime_config = config or load_runtime_config()
    approval = approval_config or load_approval_config()
    if approval.mode != "telegram":
        raise EnvironmentError("Telegram bot requires APPROVAL_MODE=telegram")

    repo = repository or build_repository()
    afip_provider = build_afip_provider(runtime_config)
    telegram = TelegramApprovalProvider(approval)

    return TelegramApprovalBot(
        approval_config=approval,
        telegram=telegram,
        afip_provider=afip_provider,
        repository=repo,
        issue_invoice=build_issue_invoice_use_case(afip_provider, repo),
        reject_payment=build_reject_payment_use_case(repo),
        postpone_payment=build_postpone_payment_use_case(repo),
    )


def run_telegram_bot_loop() -> None:
    """Poll Telegram until interrupted or a recoverable HTTP error occurs."""
    bot = create_telegram_bot()
    bot.run()


def start_telegram_bot_thread() -> TelegramBotStartResult:
    """Start the Telegram bot thread, reusing it when already running in this process."""
    global _telegram_bot_thread

    with _telegram_bot_lock:
        if _telegram_bot_thread is not None and _telegram_bot_thread.is_alive():
            logger.info(
                "El bot de Telegram ya está activo en esta aplicación — "
                "reutilizando la conexión existente."
            )
            return TelegramBotStartResult(
                thread=_telegram_bot_thread,
                reused_existing=True,
            )

        thread = threading.Thread(
            target=run_telegram_bot_loop,
            name="telegram-approval-bot",
            daemon=True,
        )
        thread.start()
        _telegram_bot_thread = thread
        return TelegramBotStartResult(thread=thread, reused_existing=False)
