import logging

from ...domain.config import LogLevel, ObservabilityConfig

_LEVELS: dict[LogLevel, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


class LogfireObservabilityBackend:
    """Sends logs to Pydantic Logfire via its logging integration."""

    def __init__(self, config: ObservabilityConfig) -> None:
        self._config = config

    def configure(self) -> None:
        try:
            import logfire
        except ImportError as exc:
            raise ImportError("logfire is not installed. Run: uv sync --extra logfire") from exc

        logfire.configure(
            token=self._config.logfire_token,
            service_name=self._config.service_name,
        )

        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(_LEVELS[self._config.log_level])

        handler = logfire.LogfireLoggingHandler()
        handler.setLevel(_LEVELS[self._config.log_level])
        root.addHandler(handler)
