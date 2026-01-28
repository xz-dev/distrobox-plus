"""distrobox-stop command implementation.

Stops one or more distrobox containers.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING

from ..config import VERSION, Config, DEFAULT_NAME, check_sudo_doas
from ..container import detect_container_manager
from ..utils import prompt_yes_no, InvalidInputError
from .list import list_containers

if TYPE_CHECKING:
    from ..container import ContainerManager


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-stop."""
    parser = argparse.ArgumentParser(
        prog="distrobox-stop",
        description="Stop distrobox containers",
    )
    parser.add_argument(
        "containers",
        nargs="*",
        help="Container name(s) to stop",
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Stop all distroboxes",
    )
    parser.add_argument(
        "-Y", "--yes",
        action="store_true",
        help="Non-interactive, stop without asking",
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


def get_all_distrobox_names(manager: ContainerManager) -> list[str]:
    """Get names of all distrobox containers.

    Args:
        manager: Container manager

    Returns:
        List of container names
    """
    containers = list_containers(manager)
    return [c["name"] for c in containers]


def stop_container(manager: ContainerManager, name: str) -> int:
    """Stop a single container with output passthrough.

    Args:
        manager: Container manager
        name: Container name

    Returns:
        Exit code from container manager
    """
    return manager.run_interactive("stop", name)


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-stop command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
        prog = os.path.basename(sys.argv[0])
        args_str = " ".join(sys.argv[1:])
        print(
            f"Running {prog} via SUDO/DOAS is not supported. "
            "Instead, please try running:",
            file=sys.stderr,
        )
        print(f"  {prog} --root {args_str}", file=sys.stderr)
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
    if parsed.yes:
        config.non_interactive = True

    # Detect container manager
    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    # Determine which containers to stop
    container_names: list[str] = []

    if parsed.all:
        container_names = get_all_distrobox_names(manager)
        if not container_names:
            print("No containers found.", file=sys.stderr)
            return 0
    elif parsed.containers:
        container_names = parsed.containers
    else:
        # Use default or config name
        name = config.container_name or DEFAULT_NAME
        container_names = [name]

    # Prompt for confirmation
    names_str = " ".join(container_names)
    if not config.non_interactive:
        try:
            if not prompt_yes_no(f"Do you really want to stop {names_str}?"):
                print("Aborted.")
                return 0
        except InvalidInputError as e:
            print(e, file=sys.stderr)
            print("Exiting.", file=sys.stderr)
            return 1

    # Stop containers
    exit_code = 0
    for name in container_names:
        ret = stop_container(manager, name)
        if ret != 0:
            exit_code = ret

    return exit_code


if __name__ == "__main__":
    sys.exit(run())
