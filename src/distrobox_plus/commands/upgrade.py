"""distrobox-upgrade command implementation.

Upgrades distrobox containers by running the entrypoint in upgrade mode.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import VERSION, Config, check_sudo_doas
from ..container import detect_container_manager
from ..utils.console import print_error, red
from .list import list_containers

if TYPE_CHECKING:
    from ..container import ContainerManager


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-upgrade."""
    epilog = """\
Examples:
    distrobox-upgrade container-name
    distrobox-upgrade --all
    distrobox-upgrade --all --running
"""

    parser = argparse.ArgumentParser(
        prog="distrobox-upgrade",
        description=f"distrobox version: {VERSION}\n\n"
        "Upgrade one or more distrobox containers.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "containers",
        nargs="*",
        help="Name(s) of container(s) to upgrade",
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="perform for all distroboxes",
    )
    parser.add_argument(
        "--running",
        action="store_true",
        help="perform only for running distroboxes",
    )
    parser.add_argument(
        "-r", "--root",
        action="store_true",
        help="launch podman/docker/lilipod with root privileges. Note that if you need root this is the preferred "
        "way over \"sudo distrobox\" (note: if using a program other than 'sudo' for root privileges is necessary, "
        "specify it through the DBX_SUDO_PROGRAM env variable, or 'distrobox_sudo_program' config variable)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="show more verbosity",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"distrobox: {VERSION}",
    )

    return parser


def _print_sudo_error() -> int:
    """Print error message when running via sudo/doas."""
    prog_name = Path(sys.argv[0]).name
    orig_args = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    print_error(
        f"Running {prog_name} via SUDO/DOAS is not supported. "
        f"Instead, please try running:"
    )
    print_error(f"  {prog_name} --root {orig_args}")
    return 1


def _get_all_containers(manager: ContainerManager) -> list[str]:
    """Get list of all distrobox container names.

    Uses list_containers() to match behavior of original shell script
    which calls distrobox-list.

    Args:
        manager: Container manager to use

    Returns:
        List of container names
    """
    containers = list_containers(manager, no_color=True)
    return [c["name"] for c in containers]


def _get_running_containers(manager: ContainerManager) -> list[str]:
    """Get list of running distrobox container names.

    Uses list_containers() to match behavior of original shell script
    which calls distrobox-list and filters with: grep -iE '| running|up'

    Args:
        manager: Container manager to use

    Returns:
        List of running container names
    """
    containers = list_containers(manager, no_color=True)
    running = []
    for c in containers:
        status = c["status"].lower()
        # Match original: grep -iE '\| running|up'
        if "running" in status or "up" in status:
            running.append(c["name"])
    return running


def _upgrade_container(
    container: str,
    extra_flags: list[str],
) -> int:
    """Upgrade a single container.

    Runs the entrypoint in upgrade mode inside the container.
    Original command:
        distrobox-enter container -- sh -c \
            "command -v su-exec && su-exec root /usr/bin/entrypoint --upgrade || \
             command -v doas && doas /usr/bin/entrypoint --upgrade || \
             sudo -S /usr/bin/entrypoint --upgrade"

    Args:
        container: Container name
        extra_flags: Extra flags (--verbose, --root)

    Returns:
        Exit code
    """
    # Print upgrade message in red bold like original (rich handles TTY detection)
    print_error(red(f" Upgrading {container}..."))

    # Build the upgrade command
    # Original: command -v su-exec && su-exec root /usr/bin/entrypoint --upgrade ||
    #           command -v doas && doas /usr/bin/entrypoint --upgrade ||
    #           sudo -S /usr/bin/entrypoint --upgrade
    upgrade_cmd = (
        "command -v su-exec 2>/dev/null && su-exec root /usr/bin/entrypoint --upgrade || "
        "command -v doas 2>/dev/null && doas /usr/bin/entrypoint --upgrade || "
        "sudo -S /usr/bin/entrypoint --upgrade"
    )

    # Build enter args
    from .enter import run as enter_run

    enter_args = [*extra_flags, container, "--", "sh", "-c", upgrade_cmd]
    return enter_run(enter_args)


def _build_extra_flags(config: Config) -> list[str]:
    """Build extra flags from config (--verbose, --root)."""
    extra_flags: list[str] = []
    if config.verbose:
        extra_flags.append("--verbose")
    if config.rootful:
        extra_flags.append("--root")
    return extra_flags


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-upgrade command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
        return _print_sudo_error()

    if args is None:
        args = sys.argv[1:]

    # If no arguments, show help and exit (like original)
    if not args:
        parser = create_parser()
        parser.print_help()
        return 0

    # Parse arguments
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Load config and apply overrides
    config = Config.load()
    if parsed.root:
        config.rootful = True
    if parsed.verbose:
        config.verbose = True

    # Detect container manager
    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    # Determine container list
    container_names: list[str] = []

    if parsed.all:
        # Get all containers
        if parsed.running:
            # Only running containers
            container_names = _get_running_containers(manager)
        else:
            # All containers
            container_names = _get_all_containers(manager)
    else:
        # Use provided container names
        container_names = parsed.containers

    # Check if we have containers to upgrade
    # Original behavior: only error if not using --all and no containers specified
    if not container_names and not parsed.all:
        print_error("Please specify the name of the container.")
        return 1

    # If --all but no containers found, just exit successfully (nothing to upgrade)
    if not container_names:
        return 0

    # Build extra flags
    extra_flags = _build_extra_flags(config)

    # Upgrade each container
    exit_code = 0
    for container in container_names:
        result = _upgrade_container(container, extra_flags)
        if result != 0:
            exit_code = result

    return exit_code


if __name__ == "__main__":
    sys.exit(run())
