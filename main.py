"""Entry point for the nightly MercadoPago → AFIP invoicing pipeline.

Copyright (c) 2026 Damian Debortoli — https://www.ddebortoli.dev/
Contact: developer.ddebortoli@gmail.com

Intended to run via cron at 23:00 ART every day:
    0 2 * * * cd /path/to/arca-automation && uv run main.py >> logs/cron.log 2>&1

When APPROVAL_MODE=telegram, run the approval bot separately:
    uv run telegram_bot.py
"""

import logging
import sys
from pathlib import Path

from src.domain.exceptions import AfipValidationError
from src.pipeline import run_payment_pipeline

_LOGS_DIR = Path(__file__).parent / "logs"


def main() -> None:
    """Bootstrap all dependencies and run the payment processing pipeline."""
    _LOGS_DIR.mkdir(exist_ok=True)
    try:
        run_payment_pipeline()
    except AfipValidationError as exc:
        logging.critical("AFIP certificate/config validation: FAILED: %s", exc)
        sys.exit(2)
    except (EnvironmentError, ValueError, ImportError) as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
