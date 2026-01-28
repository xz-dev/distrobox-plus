"""distrobox-list command implementation.

Lists all distrobox containers with their status.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from ..config import VERSION, Config, check_sudo_doas
from ..container import detect_container_manager
from ..utils import GREEN, YELLOW, CLEAR, is_tty

if TYPE_CHECKING:
    from ..container import ContainerManager


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-list."""
    parser = argparse.ArgumentParser(
        prog="distrobox-list",
        description="List all distrobox containers",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable color formatting",
    )
    parser.add_argument(
        "-r", "--root",
        action="store_true",
        help="Launch container manager with root privileges",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show more verbosity",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"distrobox: {VERSION}",
    )
    return parser


def list_containers(
    manager: ContainerManager,
    no_color: bool = False,
) -> list[dict[str, str]]:
    """Get list of distrobox containers.

    Args:
        manager: Container manager to use
        no_color: Disable color output

    Returns:
        List of container dicts with id, name, status, image keys
    """
    # Get container list with custom format including mounts to detect distrobox
    format_str = "{{.ID}}|{{.Image}}|{{.Names}}|{{.Status}}|{{.Labels}}{{.Mounts}}"
    output = manager.ps(all_=True, format_=format_str, no_trunc=True)

    containers = []
    for line in output.strip().splitlines():
        if not line:
            continue

        # Check if this is a distrobox container (has distrobox in labels/mounts)
        if "distrobox" not in line:
            continue

        parts = line.split("|")
        if len(parts) < 4:
            continue

        container = {
            "id": parts[0][:12],  # Truncate ID to 12 chars
            "image": parts[1],
            "name": parts[2],
            "status": parts[3],
        }
        containers.append(container)

    return containers


def print_containers(
    containers: list[dict[str, str]],
    no_color: bool = False,
) -> None:
    """Print container list in formatted table.

    Args:
        containers: List of container dicts
        no_color: Disable color output
    """
    use_color = is_tty() and not no_color

    # Print header
    print(
        f"{'ID':<12} | {'NAME':<20} | {'STATUS':<18} | {'IMAGE':<30}"
    )

    for container in containers:
        container_id = container["id"]
        name = container["name"]
        status = container["status"]
        image = container["image"]

        # Determine color based on status
        line = f"{container_id:<12} | {name:<20} | {status:<18} | {image:<30}"

        if use_color:
            # Running containers in green, others in yellow
            if "Up" in status or "running" in status.lower():
                print(f"{GREEN}{line}{CLEAR}")
            else:
                print(f"{YELLOW}{line}{CLEAR}")
        else:
            print(line)


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-list command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
        print(
            f"Running {sys.argv[0]} via SUDO/DOAS is not supported.",
            file=sys.stderr,
        )
        print(
            f"Instead, please try running:\n  {sys.argv[0]} --root",
            file=sys.stderr,
        )
        return 1

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

    # Detect container manager
    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    # List containers
    containers = list_containers(manager, no_color=parsed.no_color)

    # Print results
    print_containers(containers, no_color=parsed.no_color)

    return 0


if __name__ == "__main__":
    sys.exit(run())
