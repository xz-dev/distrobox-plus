"""distrobox-generate-entry command implementation.

Generates a desktop entry for a distrobox container.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import platformdirs

from .. import COMMAND_NAME
from ..config import VERSION, Config, check_sudo_doas
from ..container import ContainerManager, detect_container_manager

# Distro to icon URL mapping (same as original)
DISTRO_ICON_MAP = {
    "alma": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/alma-distrobox.png",
    "alpine": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/alpine-distrobox.png",
    "alt": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/alt-distrobox.png",
    "arch": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/arch-distrobox.png",
    "centos": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/centos-distrobox.png",
    "clear--os": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/clear-distrobox.png",
    "debian": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/debian-distrobox.png",
    "deepin": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/deepin-distrobox.png",
    "fedora": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/fedora-distrobox.png",
    "gentoo": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/gentoo-distrobox.png",
    "kali": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/kali-distrobox.png",
    "kdeneon": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/kdeneon-distrobox.png",
    "opensuse-leap": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/opensuse-distrobox.png",
    "opensuse-tumbleweed": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/opensuse-distrobox.png",
    "rhel": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/redhat-distrobox.png",
    "rocky": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/rocky-distrobox.png",
    "ubuntu": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/ubuntu-distrobox.png",
    "vanilla": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/vanilla-distrobox.png",
    "void": "https://raw.githubusercontent.com/89luca89/distrobox/main/docs/assets/png/distros/void-distrobox.png",
}

DEFAULT_ICON_URL = "https://raw.githubusercontent.com/89luca89/distrobox/main/icons/terminal-distrobox-icon.svg"


def _get_xdg_data_home() -> Path:
    """Get XDG_DATA_HOME directory."""
    return Path(platformdirs.user_data_dir())


def _get_default_icon_path() -> Path:
    """Get default icon path."""
    return _get_xdg_data_home() / "icons" / "terminal-distrobox-icon.svg"


def _get_applications_dir() -> Path:
    """Get applications directory."""
    return _get_xdg_data_home() / "applications"


def _get_icons_dir() -> Path:
    """Get distrobox icons directory."""
    return _get_xdg_data_home() / "icons" / "distrobox"


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-generate-entry."""
    parser = argparse.ArgumentParser(
        prog="distrobox-generate-entry",
        description=f"distrobox version: {VERSION}\n\n"
        "Generate a desktop entry for a distrobox container.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "container_name",
        nargs="?",
        default="",
        help="name of the container (default: my-distrobox)",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        dest="all_containers",
        help="perform for all distroboxes",
    )
    parser.add_argument(
        "-d",
        "--delete",
        action="store_true",
        help="delete the entry",
    )
    parser.add_argument(
        "-i",
        "--icon",
        default="auto",
        help="specify a custom icon [/path/to/icon] (default: auto)",
    )
    parser.add_argument(
        "-r",
        "--root",
        action="store_true",
        help="perform on rootful distroboxes",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show more verbosity",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"distrobox: {VERSION}",
    )
    return parser


def _print_sudo_error() -> int:
    """Print error message when running via sudo/doas."""
    prog_name = Path(sys.argv[0]).name
    orig_args = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    print(
        f"Running {prog_name} via SUDO/DOAS is not supported. "
        f"Instead, please try running:",
        file=sys.stderr,
    )
    print(
        f"  {prog_name} --root {orig_args}",
        file=sys.stderr,
    )
    return 1


def _get_download_command() -> list[str] | None:
    """Get download command (curl or wget).

    Returns:
        Command list for downloading, or None if neither available.
    """
    if shutil.which("curl"):
        return ["curl", "--connect-timeout", "3", "--retry", "1", "-sLo"]
    if shutil.which("wget"):
        return ["wget", "--timeout=3", "--tries=1", "-qO"]
    return None


def _download_file(url: str, output_path: Path, download_cmd: list[str]) -> bool:
    """Download a file from URL.

    Args:
        url: URL to download from
        output_path: Path to save file
        download_cmd: Download command base (curl or wget)

    Returns:
        True if successful
    """
    try:
        cmd = [*download_cmd, str(output_path), url]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _get_container_distro(
    manager: ContainerManager,
    container_name: str,
    config: Config,
) -> str | None:
    """Get distribution ID from container's /etc/os-release.

    Args:
        manager: Container manager
        container_name: Container name
        config: Config for sudo program

    Returns:
        Distribution ID or None
    """
    # Build cp command
    # Note: --log-level is already in manager.cmd_prefix if verbose
    cp_args = ["cp"]

    # Docker uses -L flag for cp
    if manager.is_docker:
        cp_args.append("-L")

    # Create temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".os-release",
        prefix=f"{container_name}.",
        delete=False,
    ) as tmp:
        tmp_path = tmp.name

    try:
        # Copy /etc/os-release from container
        cmd = [
            *manager.cmd_prefix,
            *cp_args,
            f"{container_name}:/etc/os-release",
            tmp_path,
        ]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            return None

        # Parse os-release for ID
        content = Path(tmp_path).read_text()
        for line in content.splitlines():
            if line.startswith("ID="):
                distro_id = line[3:].strip().strip('"').strip("'")
                # Remove "linux" suffix like original
                distro_id = distro_id.replace("linux", "").strip()
                return distro_id

        return None

    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        # Clean up temp file
        try:
            if config.rootful:
                subprocess.run(
                    [config.sudo_program, "rm", "-f", tmp_path], capture_output=True
                )
            else:
                os.unlink(tmp_path)
        except OSError:
            pass


def _resolve_icon(
    icon: str,
    container_name: str,
    manager: ContainerManager,
    config: Config,
) -> str:
    """Resolve icon path, downloading if needed.

    Args:
        icon: Icon value ("auto" or path)
        container_name: Container name
        manager: Container manager
        config: Config

    Returns:
        Path to icon
    """
    default_icon = str(_get_default_icon_path())

    # If not auto, use provided path
    if icon != "auto":
        return icon

    # Check for download tool
    download_cmd = _get_download_command()
    if download_cmd is None:
        print(
            "Icon generation depends on either curl or wget",
            file=sys.stderr,
        )
        print(
            "Fallbacking to default icon.",
            file=sys.stderr,
        )
        return default_icon

    # Try to detect container distribution
    container_distro = _get_container_distro(manager, container_name, config)

    icon_url: str
    if container_distro is None:
        container_distro = "terminal-distrobox-icon"
        icon_url = DEFAULT_ICON_URL
    else:
        # Look up icon URL
        maybe_url = DISTRO_ICON_MAP.get(container_distro)
        if maybe_url is None:
            print(
                "Warning: Distribution not found in default icon set. "
                "Defaulting to generic one.",
                file=sys.stderr,
            )
            container_distro = "terminal-distrobox-icon"
            icon_url = DEFAULT_ICON_URL
        else:
            icon_url = maybe_url

    # Ensure icons directory exists
    icons_dir = _get_icons_dir()
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Get icon extension
    icon_extension = icon_url.rsplit(".", 1)[-1] if "." in icon_url else "png"
    icon_path = icons_dir / f"{container_distro}.{icon_extension}"

    # Download icon
    if _download_file(icon_url, icon_path, download_cmd):
        return str(icon_path)

    # Download failed
    print(
        "Warning: Failed to download icon. Defaulting to generic one.",
        file=sys.stderr,
    )
    return default_icon


def _capitalize_first(name: str) -> str:
    """Capitalize first letter of name (like original shell script).

    Original: $(echo "${container_name}" | cut -c1 | tr "[:lower:]" "[:upper:]")$(echo "${container_name}" | cut -c2-)
    """
    if not name:
        return name
    return name[0].upper() + name[1:]


def _generate_desktop_entry(
    container_name: str,
    icon: str,
    extra_flags: str,
) -> str:
    """Generate desktop entry content.

    Args:
        container_name: Container name
        icon: Icon path
        extra_flags: Extra flags for distrobox commands

    Returns:
        Desktop entry content
    """
    entry_name = _capitalize_first(container_name)

    return f"""\
[Desktop Entry]
Name={entry_name}
GenericName=Terminal entering {entry_name}
Comment=Terminal entering {entry_name}
Categories=Distrobox;System;Utility
Exec=/bin/env {COMMAND_NAME} enter {extra_flags} {container_name}
Icon={icon}
Keywords=distrobox;
NoDisplay=false
Terminal=true
TryExec={COMMAND_NAME}
Type=Application
Actions=Remove;

[Desktop Action Remove]
Name=Remove {entry_name} from system
Exec=/bin/env {COMMAND_NAME} rm {extra_flags} {container_name}
"""


def _delete_entry(container_name: str) -> int:
    """Delete desktop entry for container.

    Args:
        container_name: Container name

    Returns:
        Exit code
    """
    desktop_file = _get_applications_dir() / f"{container_name}.desktop"
    try:
        desktop_file.unlink(missing_ok=True)
    except OSError:
        pass
    return 0


def _list_distrobox_containers(config: Config) -> list[str]:
    """List all distrobox container names.

    Args:
        config: Config

    Returns:
        List of container names
    """
    # Use list command to get containers
    from .list import list_containers

    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    containers = list_containers(manager)
    return [c["name"] for c in containers]


def _generate_entry(
    container_name: str,
    icon: str,
    config: Config,
) -> int:
    """Generate desktop entry for a single container.

    Args:
        container_name: Container name
        icon: Icon value ("auto" or path)
        config: Config

    Returns:
        Exit code
    """
    # Detect container manager
    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    # Check if container exists
    if not manager.exists(container_name):
        print(
            f"Cannot find container {container_name}. Please create it first.",
            file=sys.stderr,
        )
        return 1

    # Ensure directories exist
    _get_applications_dir().mkdir(parents=True, exist_ok=True)
    _get_icons_dir().mkdir(parents=True, exist_ok=True)

    # Build extra flags
    extra_flags = ""
    if config.rootful:
        extra_flags = "--root "

    # Resolve icon
    resolved_icon = _resolve_icon(icon, container_name, manager, config)

    # Generate desktop entry
    desktop_content = _generate_desktop_entry(
        container_name,
        resolved_icon,
        extra_flags.strip(),
    )

    # Write desktop file
    desktop_file = _get_applications_dir() / f"{container_name}.desktop"
    desktop_file.write_text(desktop_content)

    return 0


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-generate-entry command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
        return _print_sudo_error()

    # Parse arguments
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Load config
    config = Config.load()

    # Apply command line overrides
    if parsed.root:
        config.rootful = True
    if parsed.verbose:
        config.verbose = True

    # Get container name (default: my-distrobox)
    container_name = parsed.container_name or "my-distrobox"

    # Handle --all flag
    if parsed.all_containers:
        container_names = _list_distrobox_containers(config)
        for name in container_names:
            if parsed.delete:
                _delete_entry(name)
            else:
                _generate_entry(name, parsed.icon, config)
        return 0

    # Handle --delete flag
    if parsed.delete:
        return _delete_entry(container_name)

    # Generate entry
    return _generate_entry(container_name, parsed.icon, config)


if __name__ == "__main__":
    sys.exit(run())
