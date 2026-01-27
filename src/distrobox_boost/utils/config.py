"""Configuration and cache directory management using platformdirs."""

from pathlib import Path
from typing import Callable

import platformdirs

APP_NAME = "distrobox-boost"


def _ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist.

    Args:
        path: Directory path to create.

    Returns:
        The same path after ensuring it exists.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_dir(
    *,
    ensure_exists: bool = False,
    _user_config_dir: Callable[..., str] = platformdirs.user_config_dir,
) -> Path:
    """Get the base configuration directory for distrobox-boost.

    Args:
        ensure_exists: If True, create the directory if it doesn't exist.
        _user_config_dir: Function to get user config dir (for testing).

    Returns:
        Path to the config directory (e.g., ~/.config/distrobox-boost/).
    """
    path = Path(_user_config_dir(APP_NAME))
    if ensure_exists:
        _ensure_dir(path)
    return path


def get_container_config_dir(
    container_name: str,
    *,
    _user_config_dir: Callable[..., str] = platformdirs.user_config_dir,
) -> Path:
    """Get the container-specific configuration directory.

    Creates the directory if it doesn't exist.

    Args:
        container_name: Name of the distrobox container.
        _user_config_dir: Function to get user config dir (for testing).

    Returns:
        Path to the container config directory (e.g., ~/.config/distrobox-boost/mycontainer/).
    """
    config_dir = get_config_dir(ensure_exists=True, _user_config_dir=_user_config_dir)
    container_dir = config_dir / container_name
    return _ensure_dir(container_dir)


def get_container_config_file(
    container_name: str,
    *,
    _user_config_dir: Callable[..., str] = platformdirs.user_config_dir,
) -> Path:
    """Get the path to the container's distrobox.ini configuration file.

    Creates the parent directory if it doesn't exist.

    Args:
        container_name: Name of the distrobox container.
        _user_config_dir: Function to get user config dir (for testing).

    Returns:
        Path to the distrobox.ini file (e.g., ~/.config/distrobox-boost/mycontainer/distrobox.ini).
    """
    container_dir = get_container_config_dir(
        container_name, _user_config_dir=_user_config_dir
    )
    return container_dir / "distrobox.ini"


def get_cache_dir(
    *,
    ensure_exists: bool = False,
    _user_cache_dir: Callable[..., str] = platformdirs.user_cache_dir,
) -> Path:
    """Get the base cache directory for distrobox-boost.

    Args:
        ensure_exists: If True, create the directory if it doesn't exist.
        _user_cache_dir: Function to get user cache dir (for testing).

    Returns:
        Path to the cache directory (e.g., ~/.cache/distrobox-boost/).
    """
    path = Path(_user_cache_dir(APP_NAME))
    if ensure_exists:
        _ensure_dir(path)
    return path


def get_container_cache_dir(
    container_name: str,
    *,
    _user_cache_dir: Callable[..., str] = platformdirs.user_cache_dir,
) -> Path:
    """Get the container-specific cache directory.

    Creates the directory if it doesn't exist. Used for storing build files
    like Containerfile and scripts for debugging.

    Args:
        container_name: Name of the distrobox container.
        _user_cache_dir: Function to get user cache dir (for testing).

    Returns:
        Path to the container cache directory (e.g., ~/.cache/distrobox-boost/mycontainer/).
    """
    cache_dir = get_cache_dir(ensure_exists=True, _user_cache_dir=_user_cache_dir)
    container_dir = cache_dir / container_name
    return _ensure_dir(container_dir)
