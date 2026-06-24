"""Tests for Telegram bot polling conflict handling."""

from unittest.mock import MagicMock

import httpx
import pytest

from src.domain.config import ApprovalConfig
from src.providers.approval.telegram_bot_worker import (
    TelegramApprovalBot,
    _TELEGRAM_CONFLICT_MESSAGE,
)


def _build_bot() -> TelegramApprovalBot:
    approval = ApprovalConfig(
        mode="telegram",
        telegram_bot_token="123:abc",
        telegram_chat_id="-1001",
    )
    return TelegramApprovalBot(
        approval_config=approval,
        telegram=MagicMock(),
        afip_provider=MagicMock(),
        repository=MagicMock(),
        issue_invoice=MagicMock(),
        reject_payment=MagicMock(),
        postpone_payment=MagicMock(),
    )


def test_run_logs_and_stops_on_telegram_409(monkeypatch, caplog) -> None:
    bot = _build_bot()
    monkeypatch.setattr(bot, "_ensure_polling_mode", lambda: None)

    request = httpx.Request("GET", "https://api.telegram.org/bot/getUpdates")
    response = httpx.Response(status_code=409, request=request)
    monkeypatch.setattr(
        bot,
        "_poll_updates",
        lambda: (_ for _ in ()).throw(
            httpx.HTTPStatusError("conflict", request=request, response=response)
        ),
    )

    with caplog.at_level("WARNING"):
        bot.run()

    assert _TELEGRAM_CONFLICT_MESSAGE in caplog.text
