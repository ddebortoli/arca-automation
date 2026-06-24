"""Telegram bot worker for manual invoice approval.

Run as a long-lived process alongside the cron sync job:
    uv run telegram_bot.py
"""

import logging
import sys
import time

import httpx

from src.bootstrap import configure_observability, load_approval_config
from src.pipeline import run_telegram_bot_loop


def main() -> None:
    try:
        configure_observability()
    except (EnvironmentError, ValueError, ImportError) as exc:
        print(f"Observability setup failed: {exc}", file=sys.stderr)
        sys.exit(1)

    logger = logging.getLogger(__name__)

    try:
        approval_config = load_approval_config()
    except (EnvironmentError, ValueError) as exc:
        logging.critical(str(exc))
        sys.exit(1)

    if approval_config.mode != "telegram":
        logging.critical("telegram_bot.py requires APPROVAL_MODE=telegram")
        sys.exit(1)

    while True:
        try:
            run_telegram_bot_loop()
        except KeyboardInterrupt:
            logger.info("Telegram bot stopped")
            break
        except httpx.HTTPError as exc:
            logger.error("Telegram polling error: %s — retrying in 5s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
