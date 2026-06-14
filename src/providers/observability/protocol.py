from typing import Protocol


class ObservabilityPort(Protocol):
    """Contract for one-time logging/observability setup at process startup."""

    def configure(self) -> None:
        """Attach handlers and configure the root logger."""
        ...
