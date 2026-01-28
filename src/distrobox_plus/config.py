"""Configuration management for distrobox-plus.

Handles loading configuration from files and environment variables,
following the same priority as the original distrobox shell scripts.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import platformdirs

if TYPE_CHECKING:
    from collections.abc import Sequence

VERSION = "1.8.2.3"
DEFAULT_IMAGE = "registry.fedoraproject.org/fedora-toolbox:latest"
DEFAULT_NAME = "my-distrobox"


def get_config_paths() -> list[Path]:
    """Get configuration file paths in priority order (lowest to highest).

    Configuration files are loaded in order, with later files overriding earlier ones.
    Environment variables have highest priority and override all config files.

    Matches original distrobox config file search order exactly:
    1. NixOS derivation config (relative to script)
    2. /usr/share/distrobox/distrobox.conf
    3. /usr/share/defaults/distrobox/distrobox.conf
    4. /usr/etc/distrobox/distrobox.conf
    5. /usr/local/share/distrobox/distrobox.conf
    6. /etc/distrobox/distrobox.conf
    7. ${XDG_CONFIG_HOME}/distrobox/distrobox.conf
    8. ~/.distroboxrc
    """
    paths: list[Path] = []

    # Get the directory of the command itself (for NixOS compatibility)
    # Original: self_dir="$(dirname "$(realpath "$0")")"
    # Original: nix_config_file="${self_dir}/../share/distrobox/distrobox.conf"
    from .utils import get_command_path
    self_path = get_command_path()
    if self_path:
        nix_config = self_path.parent.parent / "share" / "distrobox" / "distrobox.conf"
        if nix_config.exists():
            paths.append(nix_config)

    # System-wide config locations (in original order)
    system_paths = [
        Path("/usr/share/distrobox/distrobox.conf"),
        Path("/usr/share/defaults/distrobox/distrobox.conf"),
        Path("/usr/etc/distrobox/distrobox.conf"),
        Path("/usr/local/share/distrobox/distrobox.conf"),
        Path("/etc/distrobox/distrobox.conf"),
    ]
    paths.extend(p for p in system_paths if p.exists())

    # User config: ${XDG_CONFIG_HOME:-"${HOME}/.config"}/distrobox/distrobox.conf
    user_config = Path(platformdirs.user_config_dir("distrobox")) / "distrobox.conf"
    if user_config.exists():
        paths.append(user_config)

    # Legacy user config: ~/.distroboxrc
    legacy_config = Path.home() / ".distroboxrc"
    if legacy_config.exists():
        paths.append(legacy_config)

    return paths


def parse_config_file(path: Path) -> dict[str, str]:
    """Parse a distrobox config file.

    Config files use shell-like syntax:
    - VAR=value
    - VAR="value"
    - VAR='value'
    - Comments start with #
    """
    config: dict[str, str] = {}

    try:
        content = path.read_text()
    except OSError:
        return config

    for line in content.splitlines():
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Match VAR=value patterns
        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            # Remove surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            config[key] = value

    return config


@dataclass
class Config:
    """Distrobox configuration settings.

    All values default to None, allowing detection of which were explicitly set.
    The original distrobox handles booleans as strings "true"/"false" or 0/1.
    """
    container_manager: str | None = None
    container_name: str | None = None
    container_image: str | None = None
    container_hostname: str | None = None
    container_home_prefix: str | None = None
    container_custom_home: str | None = None
    container_always_pull: bool = False
    container_generate_entry: bool = True
    container_rm_custom_home: bool = False
    non_interactive: bool = False
    verbose: bool = False
    sudo_program: str = "sudo"
    userns_nolimit: bool = False
    skip_workdir: bool = False
    clean_path: bool = False

    # Runtime state (not from config files)
    rootful: bool = field(default=False, repr=False)

    @classmethod
    def load(cls) -> Config:
        """Load configuration from files and environment variables."""
        config = cls()

        # Load from config files (in priority order)
        for path in get_config_paths():
            file_config = parse_config_file(path)
            config._apply_file_config(file_config)

        # Apply environment variables (highest priority)
        config._apply_env_vars()

        # Set rootful based on current user
        if os.getuid() == 0:
            config.rootful = True

        return config

    def _apply_file_config(self, file_config: dict[str, str]) -> None:
        """Apply config values from a parsed config file."""
        mapping = {
            "container_manager": "container_manager",
            "container_name": "container_name",
            "container_image": "container_image",
            "container_hostname": "container_hostname",
            "container_home_prefix": "container_home_prefix",
            "container_user_custom_home": "container_custom_home",
            "container_always_pull": "container_always_pull",
            "container_generate_entry": "container_generate_entry",
            "container_rm_custom_home": "container_rm_custom_home",
            "non_interactive": "non_interactive",
            "verbose": "verbose",
            "distrobox_sudo_program": "sudo_program",
            "userns_nolimit": "userns_nolimit",
            "skip_workdir": "skip_workdir",
            "clean_path": "clean_path",
        }

        for file_key, attr in mapping.items():
            if file_key in file_config:
                value = file_config[file_key]
                self._set_attr(attr, value)

    def _apply_env_vars(self) -> None:
        """Apply environment variables to config."""
        env_mapping = {
            "DBX_CONTAINER_MANAGER": "container_manager",
            "DBX_CONTAINER_NAME": "container_name",
            "DBX_CONTAINER_IMAGE": "container_image",
            "DBX_CONTAINER_HOSTNAME": "container_hostname",
            "DBX_CONTAINER_HOME_PREFIX": "container_home_prefix",
            "DBX_CONTAINER_CUSTOM_HOME": "container_custom_home",
            "DBX_CONTAINER_ALWAYS_PULL": "container_always_pull",
            "DBX_CONTAINER_GENERATE_ENTRY": "container_generate_entry",
            "DBX_CONTAINER_RM_CUSTOM_HOME": "container_rm_custom_home",
            "DBX_NON_INTERACTIVE": "non_interactive",
            "DBX_VERBOSE": "verbose",
            "DBX_SUDO_PROGRAM": "sudo_program",
            "DBX_USERNS_NOLIMIT": "userns_nolimit",
            "DBX_SKIP_WORKDIR": "skip_workdir",
            "DBX_CONTAINER_CLEAN_PATH": "clean_path",
        }

        for env_key, attr in env_mapping.items():
            value = os.environ.get(env_key)
            if value is not None:
                self._set_attr(attr, value)

    def _set_attr(self, attr: str, value: str) -> None:
        """Set attribute with type coercion."""
        current = getattr(self, attr)

        if isinstance(current, bool):
            # Handle boolean conversion (true/false/1/0)
            setattr(self, attr, value.lower() in ("true", "1", "yes"))
        else:
            setattr(self, attr, value)


def check_sudo_doas() -> bool:
    """Check if script is running via sudo/doas.

    Returns True if running via sudo/doas as root, which is not supported.
    """
    if os.getuid() != 0:
        return False

    return bool(os.environ.get("SUDO_USER") or os.environ.get("DOAS_USER"))


def get_user_info() -> tuple[str, str, str]:
    """Get current user info: (username, home, shell).

    Falls back to getent/passwd if environment variables are not set.
    Matches original distrobox behavior with /bin/bash as default shell.
    """
    import pwd

    user = os.environ.get("USER")
    home = os.environ.get("HOME")
    shell = os.environ.get("SHELL")

    if not all([user, home, shell]):
        try:
            pw = pwd.getpwuid(os.getuid())
            user = user or pw.pw_name
            home = home or pw.pw_dir
            shell = shell or pw.pw_shell
        except KeyError:
            # Fallback defaults (match original distrobox)
            user = user or "nobody"
            home = home or "/"
            shell = shell or "/bin/bash"

    # Final fallback for shell (matches original: ${SHELL:-"/bin/bash"})
    if not shell:
        shell = "/bin/bash"

    return user, home, shell  # type: ignore[return-value]
