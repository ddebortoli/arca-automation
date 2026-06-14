import logging

from ...domain.config import LogLevel, ObservabilityConfig

_LEVEL_MAP: dict[LogLevel, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


class SentryObservabilityBackend:
    """Forwards WARNING+ log records and exceptions to Sentry."""

    def __init__(self, config: ObservabilityConfig) -> None:
        self._config = config

    def configure(self) -> None:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
        except ImportError as exc:
            raise ImportError(
                "sentry-sdk is not installed. Run: uv sync --extra sentry"
            ) from exc

        level = _LEVEL_MAP[self._config.log_level]
        sentry_sdk.init(
            dsn=self._config.sentry_dsn,
            environment=self._config.service_name,
            integrations=[
                LoggingIntegration(
                    level=level,
                    event_level=logging.WARNING,
                ),
            ],
        )
