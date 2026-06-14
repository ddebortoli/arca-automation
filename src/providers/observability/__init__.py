from ...domain.config import ObservabilityConfig
from .logfire import LogfireObservabilityBackend
from .protocol import ObservabilityPort
from .sentry import SentryObservabilityBackend
from .stdio import StdioObservabilityBackend


def build_observability_backend(config: ObservabilityConfig) -> ObservabilityPort:
    """Create the observability backend configured for the current deployment."""
    backends = {
        "stdio": StdioObservabilityBackend,
        "logfire": LogfireObservabilityBackend,
        "sentry": SentryObservabilityBackend,
    }
    return backends[config.backend](config)


__all__ = [
    "LogfireObservabilityBackend",
    "SentryObservabilityBackend",
    "StdioObservabilityBackend",
    "build_observability_backend",
]
