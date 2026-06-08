from ...domain.config import ApprovalConfig
from ...domain.ports import ApprovalPort
from .auto import AutoApprovalProvider
from .telegram import TelegramApprovalProvider


def build_approval_provider(config: ApprovalConfig) -> ApprovalPort:
    """Create the approval provider configured for the current tenant."""
    if config.mode == "telegram":
        return TelegramApprovalProvider(config)
    return AutoApprovalProvider()


__all__ = [
    "AutoApprovalProvider",
    "TelegramApprovalProvider",
    "build_approval_provider",
]
