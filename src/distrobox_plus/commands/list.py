"""distrobox-list command implementation.

Lists all distrobox containers with their status.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING

from ..config import VERSION, Config, check_sudo_doas
from ..container import detect_container_manager
from ..utils.console import console, print_msg, create_container_table

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
    table = create_container_table()

    for container in containers:
        container_id = container["id"]
        name = container["name"]
        status = container["status"]
        image = container["image"]

        # Determine style based on status
        if "up" in status.lower() or "running" in status.lower():
            style = "container.running"
        else:
            style = "container.stopped"

        table.add_row(container_id, name, status, image, style=style)

    if no_color:
        console.print(table, highlight=False, style=None)
    else:
        console.print(table)


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-list command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
        prog = os.path.basename(sys.argv[0])
        orig_args = " ".join(sys.argv[1:])
        print(
            f"Running {prog} via SUDO/DOAS is not supported. "
            "Instead, please try running:",
            file=sys.stderr,
        )
        print(f"  {prog} --root {orig_args}", file=sys.stderr)
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
