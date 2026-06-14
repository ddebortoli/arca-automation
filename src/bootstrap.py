import os
from pathlib import Path

from dotenv import load_dotenv

from .domain.config import ApprovalConfig, ObservabilityConfig
from .domain.ports import AfipPort, ApprovalPort, MercadoPagoPort
from .providers.afip import AfipAuthProvider, AfipElectronicBillingProvider
from .providers.approval import build_approval_provider
from .providers.mercadopago import HttpMercadoPagoProvider
from .providers.observability import build_observability_backend
from .repositories.payment_repository import PaymentRepository
from .use_cases.issue_invoice import IssueInvoiceUseCase
from .use_cases.process_payments import ProcessPaymentsUseCase
from .use_cases.postpone_payment import PostponePaymentUseCase
from .use_cases.reject_payment import RejectPaymentUseCase


def load_runtime_config() -> dict[str, str]:
    """Load required environment variables for the single-tenant deployment."""
    load_dotenv()
    required = ("MP_ACCESS_TOKEN", "MP_USER_ID", "AFIP_CUIT", "AFIP_CERT_PATH", "AFIP_KEY_PATH")
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
    load_dotenv()
    backend = os.getenv("OBSERVABILITY_BACKEND", "stdio")
    if backend not in {"stdio", "logfire", "sentry"}:
        raise EnvironmentError(
            "OBSERVABILITY_BACKEND must be 'stdio', 'logfire', or 'sentry'"
        )

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
    build_observability_backend(config).configure()


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


def build_repository(db_path: Path) -> PaymentRepository:
    return PaymentRepository(db_path=db_path)


def build_process_payments_use_case(
    *,
    mp_provider: MercadoPagoPort,
    afip_provider: AfipPort,
    approval_provider: ApprovalPort,
    repository: PaymentRepository,
) -> ProcessPaymentsUseCase:
    return ProcessPaymentsUseCase(
        mp_provider=mp_provider,
        afip_provider=afip_provider,
        approval_provider=approval_provider,
        repository=repository,
    )


def build_issue_invoice_use_case(
    afip_provider: AfipPort,
    repository: PaymentRepository,
) -> IssueInvoiceUseCase:
    return IssueInvoiceUseCase(afip_provider, repository)


def build_reject_payment_use_case(
    repository: PaymentRepository,
) -> RejectPaymentUseCase:
    return RejectPaymentUseCase(repository)


def build_postpone_payment_use_case(
    repository: PaymentRepository,
) -> PostponePaymentUseCase:
    return PostponePaymentUseCase(repository)
