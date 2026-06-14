import logging
from unittest.mock import MagicMock, patch

import pytest

from src.bootstrap import _TelegramApiLogFilter, _redact_telegram_bot_token
from src.domain.config import ObservabilityConfig
from src.providers.observability import build_observability_backend
from src.providers.observability.stdio import StdioObservabilityBackend


def test_observability_config_defaults_to_stdio() -> None:
    config = ObservabilityConfig()
    assert config.backend == "stdio"
    assert config.service_name == "arca-automation"
    assert config.log_level == "INFO"


def test_observability_config_logfire_requires_token() -> None:
    with pytest.raises(ValueError, match="logfire_token"):
        ObservabilityConfig(backend="logfire")


def test_observability_config_sentry_requires_dsn() -> None:
    with pytest.raises(ValueError, match="sentry_dsn"):
        ObservabilityConfig(backend="sentry")


def test_stdio_backend_configures_root_logger() -> None:
    config = ObservabilityConfig(backend="stdio", log_level="DEBUG")
    backend = StdioObservabilityBackend(config)

    backend.configure()

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1


def test_build_observability_backend_returns_stdio_by_default() -> None:
    backend = build_observability_backend(ObservabilityConfig())
    assert isinstance(backend, StdioObservabilityBackend)


def test_logfire_backend_calls_configure() -> None:
    config = ObservabilityConfig(
        backend="logfire",
        logfire_token="test-token",
        service_name="test-service",
    )
    mock_logfire = MagicMock()
    mock_handler = MagicMock()
    mock_handler.level = logging.NOTSET

    def _set_level(level: int) -> None:
        mock_handler.level = level

    mock_handler.setLevel.side_effect = _set_level
    mock_logfire.LogfireLoggingHandler.return_value = mock_handler

    with patch.dict("sys.modules", {"logfire": mock_logfire}):
        backend = build_observability_backend(config)
        backend.configure()

    mock_logfire.configure.assert_called_once_with(
        token="test-token",
        service_name="test-service",
    )
    assert mock_logfire.LogfireLoggingHandler.called

    # Avoid leaking log handlers into subsequent tests.
    logging.getLogger().handlers.clear()


def test_logfire_backend_raises_when_not_installed() -> None:
    config = ObservabilityConfig(backend="logfire", logfire_token="test-token")

    with patch.dict("sys.modules", {"logfire": None}):
        backend = build_observability_backend(config)
        with pytest.raises(ImportError, match="uv sync --extra logfire"):
            backend.configure()


def test_sentry_backend_calls_init() -> None:
    config = ObservabilityConfig(
        backend="sentry",
        sentry_dsn="https://example@sentry.io/1",
        service_name="test-service",
        log_level="INFO",
    )
    mock_sentry = MagicMock()
    mock_integration = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "sentry_sdk": mock_sentry,
            "sentry_sdk.integrations": MagicMock(),
            "sentry_sdk.integrations.logging": MagicMock(
                LoggingIntegration=mock_integration
            ),
        },
    ):
        backend = build_observability_backend(config)
        backend.configure()

    mock_sentry.init.assert_called_once()
    call_kwargs = mock_sentry.init.call_args.kwargs
    assert call_kwargs["dsn"] == "https://example@sentry.io/1"
    assert call_kwargs["environment"] == "test-service"


def test_redact_telegram_bot_token_redacts_any_endpoint() -> None:
    message = (
        'HTTP Request: POST https://api.telegram.org/bot123456:abcDEF/sendMessage '
        '"HTTP/1.1 200 OK"'
    )
    redacted = _redact_telegram_bot_token(message)
    assert "abcDEF" not in redacted
    assert "bot123456:<redacted>/sendMessage" in redacted


def test_telegram_api_filter_redacts_and_keeps_non_polling_logs() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=(
            'HTTP Request: POST https://api.telegram.org/bot123456:abcDEF/sendMessage '
            '"HTTP/1.1 200 OK"'
        ),
        args=(),
        exc_info=None,
    )

    allow = _TelegramApiLogFilter().filter(record)
    assert allow is True
    assert "abcDEF" not in record.getMessage()
    assert "bot123456:<redacted>/sendMessage" in record.getMessage()


def test_telegram_api_filter_drops_successful_get_updates() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=(
            'HTTP Request: GET https://api.telegram.org/bot123456:abcDEF/getUpdates '
            '"HTTP/1.1 200 OK"'
        ),
        args=(),
        exc_info=None,
    )

    allow = _TelegramApiLogFilter().filter(record)
    assert allow is False
    assert "abcDEF" not in record.getMessage()
