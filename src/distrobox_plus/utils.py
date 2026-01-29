"""Shared utility functions for distrobox-plus."""

from __future__ import annotations

import importlib.resources
import os
import re
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# ANSI color codes
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[1;31m"  # Bold red
CLEAR = "\033[0m"


class InvalidInputError(Exception):
    """Raised when user provides invalid input to a prompt."""

    pass


def is_tty() -> bool:
    """Check if stdin and stdout are connected to a TTY."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def colorize(text: str, color: str, force: bool = False) -> str:
    """Apply ANSI color to text if in TTY.

    Args:
        text: Text to colorize
        color: ANSI color code
        force: Force color even if not in TTY

    Returns:
        Colorized text or original text if not in TTY
    """
    if force or is_tty():
        return f"{color}{text}{CLEAR}"
    return text


def green(text: str) -> str:
    """Color text green."""
    return colorize(text, GREEN)


def yellow(text: str) -> str:
    """Color text yellow."""
    return colorize(text, YELLOW)


def red(text: str) -> str:
    """Color text red."""
    return colorize(text, RED)


def print_ok(message: str = "OK") -> None:
    """Print OK status in green."""
    print(f" {green(f'[ {message} ]')}", file=sys.stderr)


def print_err(message: str = "ERR") -> None:
    """Print error status in red."""
    print(f" {red(f'[ {message} ]')}", file=sys.stderr)


def print_warning(message: str) -> None:
    """Print warning message in yellow."""
    print(yellow(f"Warning: {message}"), file=sys.stderr)


def print_error(message: str) -> None:
    """Print error message in red."""
    print(red(f"Error: {message}"), file=sys.stderr)


def print_status(message: str, end: str = "\t") -> None:
    """Print status message to stderr."""
    print(f"%-40s{end}" % message, file=sys.stderr, end="")


def prompt_yes_no(
    message: str,
    default: bool = True,
    non_interactive: bool = False,
) -> bool:
    """Prompt user for yes/no confirmation.

    Args:
        message: Prompt message
        default: Default value if user presses enter
        non_interactive: Skip prompt and return default

    Returns:
        True for yes, False for no

    Raises:
        InvalidInputError: If user provides invalid input
    """
    if non_interactive:
        return True

    default_str = "Y/n" if default else "y/N"
    try:
        response = input(f"{message} [{default_str}]: ").strip().lower()
    except EOFError:
        return default

    if not response:
        return default

    if response in ("y", "yes"):
        return True
    if response in ("n", "no"):
        return False

    # Invalid input - raise exception like original shell script
    raise InvalidInputError(
        "Invalid input.\n"
        "The available choices are: y,Y,Yes,yes,YES or n,N,No,no,NO."
    )


def get_command_path() -> Path | None:
    """Get path to the current command binary.

    Tries to find the current command (distrobox-plus or distrobox)
    by checking sys.argv[0] first, then searching PATH.

    Returns:
        Path to the command binary or None if not found
    """
    from . import COMMAND_NAME

    # First try sys.argv[0] if it's an absolute path
    if sys.argv and os.path.isabs(sys.argv[0]):
        argv_path = Path(os.path.realpath(sys.argv[0]))
        if argv_path.exists():
            return argv_path

    # Try to find current command in PATH
    cmd_path = shutil.which(COMMAND_NAME)
    if cmd_path:
        return Path(os.path.realpath(cmd_path))

    return None


def get_script_path(script_name: str) -> Path | None:
    """Get path to a distrobox script.

    Checks in order:
    1. Bundled scripts in the package
    2. Same directory as current command
    3. System PATH

    Args:
        script_name: Name of the script (e.g., "distrobox-init")

    Returns:
        Path to script or None if not found
    """
    # First check bundled scripts in the package
    try:
        from . import scripts

        files = importlib.resources.files(scripts)
        script_file = files.joinpath(script_name)
        # Check if the script exists in the package
        with importlib.resources.as_file(script_file) as path:
            if path.exists():
                return Path(path)
    except (ImportError, TypeError, FileNotFoundError):
        pass

    # Then check relative to current command binary
    cmd_path = get_command_path()
    if cmd_path:
        same_dir = cmd_path.parent / script_name
        if same_dir.exists():
            return same_dir

    # Fall back to PATH lookup
    path = shutil.which(script_name)
    return Path(path) if path else None


def derive_container_name(image: str) -> str:
    """Derive a container name from an image name.

    Examples:
        alpine -> alpine
        ubuntu:20.04 -> ubuntu-20.04
        registry.fedoraproject.org/fedora-toolbox:39 -> fedora-toolbox-39
        ghcr.io/void-linux/void-linux:latest-full-x86_64 -> void-linux-latest-full-x86_64

    Args:
        image: Container image name

    Returns:
        Derived container name
    """
    # Get basename of image
    name = Path(image).name
    # Replace : and . with -
    name = re.sub(r'[:.]', '-', name)
    return name


def get_hostname() -> str:
    """Get the system hostname."""
    import socket
    return socket.gethostname()


def validate_hostname(hostname: str) -> bool:
    """Validate that hostname is <= 64 characters.

    Args:
        hostname: Hostname to validate

    Returns:
        True if valid
    """
    return len(hostname) <= 64


def find_ro_mountpoints() -> set[str]:
    """Find read-only mountpoints in the system.

    Returns:
        Set of paths that are mounted read-only
    """
    ro_mounts: set[str] = set()

    try:
        # Use findmnt to get mount options
        import subprocess
        result = subprocess.run(
            ["findmnt", "--noheadings", "--list", "--output", "TARGET,OPTIONS"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    target, options = parts
                    # Check if 'ro' is in options
                    if re.search(r'\bro\b', options):
                        ro_mounts.add(target)
    except (OSError, subprocess.SubprocessError):
        pass

    return ro_mounts


def is_symlink(path: str) -> bool:
    """Check if path is a symlink."""
    return os.path.islink(path)


def get_real_path(path: str) -> str:
    """Get real path resolving symlinks."""
    return os.path.realpath(path)


def file_exists(path: str) -> bool:
    """Check if file or directory exists."""
    return os.path.exists(path)


def is_dir(path: str) -> bool:
    """Check if path is a directory."""
    return os.path.isdir(path)


def mkdir_p(path: str | Path) -> bool:
    """Create directory and parents if needed.

    Args:
        path: Directory path

    Returns:
        True if successful
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


def remove_trailing_slashes(path: str) -> str:
    """Remove trailing slashes from path."""
    return path.rstrip("/")


def get_xdg_runtime_dir() -> Path | None:
    """Get XDG_RUNTIME_DIR for current user."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime)

    uid = os.getuid()
    default = Path(f"/run/user/{uid}")
    if default.exists():
        return default

    return None


def get_cache_dir() -> Path:
    """Get distrobox cache directory."""
    import platformdirs
    return Path(platformdirs.user_cache_dir("distrobox"))


def escape_for_shell(s: str) -> str:
    """Escape string for shell use.

    Args:
        s: String to escape

    Returns:
        Shell-escaped string
    """
    import shlex
    return shlex.quote(s)


def filter_env_for_container() -> dict[str, str]:
    """Filter environment variables suitable for passing to container.

    Filters out variables that:
    - Contain special characters like " ` $
    - Start with certain prefixes (HOME, HOST, etc.)

    Returns:
        Dict of filtered environment variables
    """
    skip_patterns = {
        "CONTAINER_ID",
        "FPATH",
        "HOST",
        "HOSTNAME",
        "HOME",
        "PATH",
        "PROFILEREAD",
        "PWD",
        "SHELL",
        "XDG_SEAT",
        "XDG_VTNR",
        "_",
    }

    # Patterns that start with these
    skip_prefixes = ("XDG_",)

    result: dict[str, str] = {}
    for key, value in os.environ.items():
        # Skip if matches pattern
        if key in skip_patterns:
            continue

        # Skip variables starting with underscore (like original ^_)
        if key.startswith("_"):
            continue

        # Skip XDG_*_DIRS but keep other XDG vars
        if key.startswith("XDG_") and key.endswith("_DIRS"):
            continue

        # Skip if contains special characters
        if any(c in value for c in ('"', '`', '$')):
            continue

        result[key] = value

    return result


def get_standard_paths() -> list[str]:
    """Get standard FHS program paths."""
    return [
        "/usr/local/sbin",
        "/usr/local/bin",
        "/usr/sbin",
        "/usr/bin",
        "/sbin",
        "/bin",
    ]


def build_container_path(
    host_path: str,
    container_path: str = "",
    clean: bool = False,
) -> str:
    """Build PATH for container entry.

    Matches original distrobox-enter behavior:
    - clean=True: container_path + standard FHS paths
    - clean=False: host_path + container_path + missing standard paths

    Args:
        host_path: Host PATH value
        container_path: Container's configured PATH (from inspect)
        clean: If True, use only container_path + standard paths

    Returns:
        PATH value for container
    """
    standard = get_standard_paths()
    host_parts = host_path.split(":") if host_path else []

    if clean:
        # Original: container_path + standard paths (not in container_path)
        result_parts = container_path.split(":") if container_path else []
        for path in standard:
            if path not in result_parts:
                result_parts.append(path)
        return ":".join(result_parts) if result_parts else ":".join(standard)

    # Collect: container_path + standard paths not in host PATH
    additional_parts = container_path.split(":") if container_path else []
    for path in standard:
        if path not in host_parts:
            if path not in additional_parts:
                additional_parts.append(path)

    if additional_parts:
        return f"{host_path}:{':'.join(additional_parts)}"
    return host_path
