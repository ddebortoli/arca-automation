from typing import Literal

from pydantic import BaseModel, model_validator

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
ObservabilityBackend = Literal["stdio", "logfire", "sentry"]


class ApprovalConfig(BaseModel):
    """Controls whether invoices require manual approval before AFIP emission."""

    mode: Literal["auto", "telegram"] = "auto"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    @model_validator(mode="after")
    def validate_telegram_settings(self) -> "ApprovalConfig":
        if self.mode == "telegram":
            if not self.telegram_bot_token or not self.telegram_chat_id:
                raise ValueError(
                    "telegram_bot_token and telegram_chat_id are required "
                    "when approval mode is 'telegram'"
                )
        return self

    @property
    def requires_manual_approval(self) -> bool:
        return self.mode == "telegram"


class ObservabilityConfig(BaseModel):
    """Controls which logging backend is configured at process startup."""

    backend: ObservabilityBackend = "stdio"
    service_name: str = "arca-automation"
    log_level: LogLevel = "INFO"
    logfire_token: str | None = None
    sentry_dsn: str | None = None

    @model_validator(mode="after")
    def validate_backend_credentials(self) -> "ObservabilityConfig":
        if self.backend == "logfire" and not self.logfire_token:
            raise ValueError("logfire_token is required when backend is 'logfire'")
        if self.backend == "sentry" and not self.sentry_dsn:
            raise ValueError("sentry_dsn is required when backend is 'sentry'")
        return self
