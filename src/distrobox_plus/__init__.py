"""distrobox-plus: A Python implementation of distrobox.

This package provides a Python translation of the distrobox shell scripts,
maintaining feature parity while leveraging Python's standard library.
"""

from importlib.metadata import metadata

from .cli import main
from .config import VERSION

__version__ = VERSION

# Get command name from pyproject.toml [project.name]
# Users who fork only need to change pyproject.toml
COMMAND_NAME = metadata(__package__)["Name"]

__all__ = ["main", "VERSION", "COMMAND_NAME"]
