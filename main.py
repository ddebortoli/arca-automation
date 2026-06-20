"""Entry point for the nightly MercadoPago → AFIP invoicing pipeline.

Intended to run via cron at 23:00 ART every day:
    0 2 * * * cd /path/to/arca-automation && uv run main.py >> logs/cron.log 2>&1

When APPROVAL_MODE=telegram, run the approval bot separately:
    uv run telegram_bot.py
"""
import logging
import os
import sys
from pathlib import Path

from src.bootstrap import (
    build_afip_provider,
    build_mercadopago_provider,
    build_process_payments_use_case,
    build_repository,
    configure_observability,
    load_approval_config,
    load_runtime_config,
)
from src.domain.exceptions import AfipValidationError
from src.providers.approval import build_approval_provider

_DB_PATH = Path(__file__).parent / "payments.db"
_LOGS_DIR = Path(__file__).parent / "logs"


def main() -> None:
    """Bootstrap all dependencies and run the payment processing pipeline."""
    _LOGS_DIR.mkdir(exist_ok=True)
    try:
        configure_observability()
    except (EnvironmentError, ValueError, ImportError) as exc:
        print(f"Observability setup failed: {exc}", file=sys.stderr)
        sys.exit(1)

    logger = logging.getLogger(__name__)

    try:
        config = load_runtime_config()
        approval_config = load_approval_config()
    except (EnvironmentError, ValueError) as exc:
        logging.critical(str(exc))
        sys.exit(1)

    repository = build_repository(_DB_PATH)
    afip_provider = build_afip_provider(config)
    if os.getenv("AFIP_VALIDATE_CERT") == "1":
        try:
            # Provider exposes a lightweight validator via FECompUltimoAutorizado.
            afip_provider.validate_configuration()
            logger.info("AFIP certificate/config validation: OK")
        except AfipValidationError as exc:
            logger.critical("AFIP certificate/config validation: FAILED: %s", exc)
            sys.exit(2)
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


if __name__ == "__main__":
    main()
