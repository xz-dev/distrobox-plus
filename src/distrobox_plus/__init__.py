"""distrobox-plus: A Python implementation of distrobox.

This package provides a Python translation of the distrobox shell scripts,
maintaining feature parity while leveraging Python's standard library.
"""

from .cli import main
from .config import VERSION

__version__ = VERSION


def _get_command_name() -> str:
    """Get command name from package metadata (pyproject.toml)."""
    try:
        from importlib.metadata import metadata

        return metadata(__package__)["Name"]
    except Exception:
        # Development mode: read from pyproject.toml directly
        from pathlib import Path

        import tomllib  # type: ignore[import-not-found]

        pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            return str(data.get("project", {}).get("name", "distrobox-plus"))
        raise


# Get command name from pyproject.toml [project.name]
# Users who fork only need to change pyproject.toml
COMMAND_NAME = _get_command_name()

__all__ = ["main", "VERSION", "COMMAND_NAME"]
