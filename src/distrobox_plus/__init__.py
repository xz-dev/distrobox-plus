"""distrobox-plus: A Python implementation of distrobox.

This package provides a Python translation of the distrobox shell scripts,
maintaining feature parity while leveraging Python's standard library.
"""

from .cli import main
from .config import VERSION

__version__ = VERSION
__all__ = ["main", "VERSION"]
