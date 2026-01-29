"""Container-side scripts for distrobox-plus.

These scripts are meant to run inside containers, not on the host.
They are packaged as resources and can be deployed to containers as needed.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path


def get_script_path(script_name: str) -> Path:
    """Get the path to a bundled script.

    Args:
        script_name: Name of the script (e.g., "distrobox-host-exec")

    Returns:
        Path to the script file

    Raises:
        FileNotFoundError: If the script doesn't exist
    """
    files = importlib.resources.files(__package__)
    script_file = files.joinpath(script_name)

    # Use as_file for proper resource handling
    with importlib.resources.as_file(script_file) as path:
        if not path.exists():
            raise FileNotFoundError(f"Script not found: {script_name}")
        return Path(path)


def get_script_content(script_name: str) -> str:
    """Get the content of a bundled script.

    Args:
        script_name: Name of the script (e.g., "distrobox-host-exec")

    Returns:
        Script content as string

    Raises:
        FileNotFoundError: If the script doesn't exist
    """
    files = importlib.resources.files(__package__)
    script_file = files.joinpath(script_name)
    return script_file.read_text()


# List of available scripts
AVAILABLE_SCRIPTS = [
    "distrobox-host-exec",
    "distrobox-init",
]
