from ...domain.config import ObservabilityConfig


class LogfireObservabilityBackend:
    """Sends logs to Pydantic Logfire via its logging integration."""

    def __init__(self, config: ObservabilityConfig) -> None:
        self._config = config

    def configure(self) -> None:
        try:
            import logfire
        except ImportError as exc:
            raise ImportError(
                "logfire is not installed. Run: uv sync --extra logfire"
            ) from exc

        logfire.configure(
            token=self._config.logfire_token,
            service_name=self._config.service_name,
        )
