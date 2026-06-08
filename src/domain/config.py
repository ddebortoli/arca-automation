from typing import Literal

from pydantic import BaseModel, model_validator


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
