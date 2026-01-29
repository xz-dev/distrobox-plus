"""Logging configuration for distrobox-plus."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Module-level logger
_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Get the package logger."""
    global _logger
    if _logger is None:
        pkg = (__package__ or __name__).split(".")[0]
        _logger = logging.getLogger(pkg)
    return _logger


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO level.
    """
    logger = get_logger()

    # Avoid adding handlers multiple times
    if logger.handlers:
        return

    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    # Console handler with simple format
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    # Format: just the message for normal use, with level for debug
    if verbose:
        fmt = "%(levelname)s: %(message)s"
    else:
        fmt = "%(message)s"

    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
