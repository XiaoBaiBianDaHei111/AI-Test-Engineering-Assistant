"""Application logging configuration."""

import logging
import sys

from app.core.config import settings

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configure_logging() -> None:
    """Configure the root logger for the whole application."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers when re-configuring in tests.
    if not root.handlers:
        root.addHandler(handler)


configure_logging()

logger = logging.getLogger("app")
