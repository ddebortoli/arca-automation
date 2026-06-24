"""Bootstrap wiring and database factory helpers."""

import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from .domain.config import ApprovalConfig, ObservabilityConfig
from .domain.ports import AfipPort, ApprovalPort, MercadoPagoPort, PaymentRepositoryPort
from .paths import get_default_sqlite_path, resolve_sqlite_path
from .providers.afip import AfipAuthProvider, AfipElectronicBillingProvider
from .providers.approval import build_approval_provider
from .providers.mercadopago import HttpMercadoPagoProvider
from .providers.observability import build_observability_backend
from .repositories.postgres_payment_repository import PostgresPaymentRepository
from .repositories.sqlite_payment_repository import SqlitePaymentRepository
from .use_cases.issue_invoice import IssueInvoiceUseCase
from .use_cases.process_payments import ProcessPaymentsUseCase
from .use_cases.postpone_payment import PostponePaymentUseCase
from .use_cases.reject_payment import RejectPaymentUseCase

_TELEGRAM_BOT_URL_PATTERN = re.compile(r"(api\.telegram\.org/bot)([^/\s\"']+)(/)")


def _load_env() -> None:
    """Load environment variables from `.env` or from `ARC_ENV_FILE`.

    If `ARC_ENV_FILE` is set, it is loaded with `override=True` so the desktop
    app's generated file takes precedence over the repo's `.env`.
    """
    arc_env_file = os.getenv("ARC_ENV_FILE")
    if arc_env_file:
        expanded = str(Path(arc_env_file).expanduser())
        load_dotenv(dotenv_path=expanded, override=True)
        return

    load_dotenv()


def _redact_telegram_bot_token(message: str) -> str:
    """Redact Telegram bot token secrets in any Bot API URL."""

    def _replace(match: re.Match[str]) -> str:
        token = match.group(2)
        token_id, _, _token_secret = token.partition(":")
        replacement = f"{token_id}:<redacted>" if token_id else "<redacted>"
        return f"{match.group(1)}{replacement}{match.group(3)}"

    return _TELEGRAM_BOT_URL_PATTERN.sub(_replace, message)


class _TelegramApiLogFilter(logging.Filter):
    """Redact Telegram tokens and drop repetitive successful polling logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "api.telegram.org/bot" not in message:
            return True

        redacted_message = _redact_telegram_bot_token(message)
        record.msg = redacted_message
        record.args = ()

        return not ("/getUpdates" in redacted_message and "200 OK" in redacted_message)


def load_runtime_config() -> dict[str, str]:
    """Load required environment variables for the single-tenant deployment."""
    _load_env()
    required = (
        "MP_ACCESS_TOKEN",
        "MP_USER_ID",
        "AFIP_CUIT",
        "AFIP_CERT_PATH",
        "AFIP_KEY_PATH",
    )
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

    return {key: os.environ[key] for key in required}


def load_approval_config() -> ApprovalConfig:
    """Load approval settings from environment variables."""
    mode = os.getenv("APPROVAL_MODE", "auto")
    if mode not in {"auto", "telegram"}:
        raise EnvironmentError("APPROVAL_MODE must be 'auto' or 'telegram'")

    return ApprovalConfig(
        mode=mode,  # type: ignore[arg-type]
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )


def load_observability_config() -> ObservabilityConfig:
    """Load observability settings from environment variables."""
    _load_env()
    backend = os.getenv("OBSERVABILITY_BACKEND", "stdio")
    if backend not in {"stdio", "logfire", "sentry"}:
        raise EnvironmentError("OBSERVABILITY_BACKEND must be 'stdio', 'logfire', or 'sentry'")

    log_level = os.getenv("LOG_LEVEL", "INFO")
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise EnvironmentError("LOG_LEVEL must be DEBUG, INFO, WARNING, or ERROR")

    return ObservabilityConfig(
        backend=backend,  # type: ignore[arg-type]
        service_name=os.getenv("SERVICE_NAME", "arca-automation"),
        log_level=log_level,  # type: ignore[arg-type]
        logfire_token=os.getenv("LOGFIRE_TOKEN"),
        sentry_dsn=os.getenv("SENTRY_DSN"),
    )


def configure_observability(config: ObservabilityConfig | None = None) -> None:
    """Configure logging for the current process."""
    if config is None:
        config = load_observability_config()

    root = logging.getLogger()
    preserved_handlers = [
        handler for handler in root.handlers if getattr(handler, "preserve_on_reconfigure", False)
    ]

    build_observability_backend(config).configure()

    for handler in preserved_handlers:
        if handler not in root.handlers:
            root.addHandler(handler)

    filter_instance = _TelegramApiLogFilter()
    for handler in root.handlers:
        if not any(isinstance(existing, _TelegramApiLogFilter) for existing in handler.filters):
            handler.addFilter(filter_instance)


def build_mercadopago_provider(config: dict[str, str]) -> MercadoPagoPort:
    return HttpMercadoPagoProvider(
        access_token=config["MP_ACCESS_TOKEN"],
        my_user_id=int(config["MP_USER_ID"]),
    )


def build_afip_provider(config: dict[str, str]) -> AfipPort:
    afip_auth = AfipAuthProvider(
        cert_path=config["AFIP_CERT_PATH"],
        key_path=config["AFIP_KEY_PATH"],
        cuit=int(config["AFIP_CUIT"]),
    )
    return AfipElectronicBillingProvider(auth=afip_auth)


def build_repository() -> PaymentRepositoryPort:
    """Build the configured payment repository from environment variables."""
    _load_env()
    backend = os.getenv("DATABASE_BACKEND", "sqlite").strip().lower()
    if backend == "sqlite":
        db_path = resolve_sqlite_path(os.getenv("DATABASE_PATH"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return SqlitePaymentRepository(db_path)

    if backend == "postgres":
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise EnvironmentError("DATABASE_URL is required when DATABASE_BACKEND=postgres")
        return PostgresPaymentRepository(database_url)

    raise EnvironmentError("DATABASE_BACKEND must be 'sqlite' or 'postgres'")


def verify_database_connection(
    *,
    backend: str,
    database_path: str = "",
    database_url: str = "",
) -> None:
    """Validate database connectivity and ensure schema exists.

    Raises:
        EnvironmentError: If configuration is invalid.
        Exception: If the connection or schema initialization fails.
    """
    normalized = backend.strip().lower()
    if normalized == "sqlite":
        path = resolve_sqlite_path(database_path or None)
        path.parent.mkdir(parents=True, exist_ok=True)
        SqlitePaymentRepository(path)
        return

    if normalized == "postgres":
        url = database_url.strip()
        if not url:
            raise EnvironmentError("DATABASE_URL is required for PostgreSQL")
        PostgresPaymentRepository(url)
        return

    raise EnvironmentError("DATABASE_BACKEND must be 'sqlite' or 'postgres'")


def get_resolved_sqlite_path() -> Path:
    """Return the SQLite path that would be used with current environment."""
    _load_env()
    return resolve_sqlite_path(os.getenv("DATABASE_PATH"))


def get_default_sqlite_database_path() -> Path:
    """Return the default SQLite database path for new installations."""
    return get_default_sqlite_path()


def build_process_payments_use_case(
    *,
    mp_provider: MercadoPagoPort,
    afip_provider: AfipPort,
    approval_provider: ApprovalPort,
    repository: PaymentRepositoryPort,
) -> ProcessPaymentsUseCase:
    return ProcessPaymentsUseCase(
        mp_provider=mp_provider,
        afip_provider=afip_provider,
        approval_provider=approval_provider,
        repository=repository,
    )


def build_issue_invoice_use_case(
    afip_provider: AfipPort,
    repository: PaymentRepositoryPort,
) -> IssueInvoiceUseCase:
    return IssueInvoiceUseCase(afip_provider, repository)


def build_reject_payment_use_case(
    repository: PaymentRepositoryPort,
) -> RejectPaymentUseCase:
    return RejectPaymentUseCase(repository)


def build_postpone_payment_use_case(
    repository: PaymentRepositoryPort,
) -> PostponePaymentUseCase:
    return PostponePaymentUseCase(repository)
