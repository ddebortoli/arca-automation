import logging
import sys
from typing import ClassVar

from ...domain.config import LogLevel, ObservabilityConfig

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"


class StdioObservabilityBackend:
    """Default backend: logs to stdout with no external dependencies."""

    _LEVELS: ClassVar[dict[LogLevel, int]] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }

    def __init__(self, config: ObservabilityConfig) -> None:
        self._config = config

    def configure(self) -> None:
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(self._LEVELS[self._config.log_level])

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(handler)
