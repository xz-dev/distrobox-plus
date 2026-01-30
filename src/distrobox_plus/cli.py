"""Command-line interface router for distrobox-plus.

Routes commands to the appropriate subcommand handlers.
"""

from __future__ import annotations

import argparse
import sys

from .config import VERSION
from .utils.console import print_error, print_msg, red
from .utils.exceptions import DistroboxError


def main(argv: list[str] | None = None) -> int:
    """Main entry point for distrobox-plus CLI.

    Routes commands to the appropriate subcommand handlers.

    Args:
        argv: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    try:
        return _main(argv)
    except DistroboxError as e:
        print_error(red(f"Error: {e}"))
        return e.exit_code


def _main(argv: list[str] | None = None) -> int:
    """Internal main function that may raise exceptions."""
    parser = argparse.ArgumentParser(
        prog="distrobox",
        description="Create and manage containerized environments",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"distrobox: {VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    subparsers.add_parser("assemble", help="Create containers from a manifest file")
    subparsers.add_parser("build", help="Build optimized container image")
    subparsers.add_parser("create", help="Create a new container")
    subparsers.add_parser("enter", help="Enter a container")
    subparsers.add_parser("ephemeral", help="Create a temporary container")
    subparsers.add_parser("export", help="Export apps/services from container to host")
    subparsers.add_parser("generate-entry", help="Generate desktop entry for container")
    subparsers.add_parser("list", aliases=["ls"], help="List containers")
    subparsers.add_parser("rm", help="Remove containers")
    subparsers.add_parser("stop", help="Stop running containers")
    subparsers.add_parser("upgrade", help="Upgrade containers")

    if argv is None:
        argv = sys.argv[1:]

    # Handle "version" as a positional command (alias for --version)
    if argv and argv[0] == "version":
        print_msg(f"distrobox: {VERSION}")
        return 0

    # Handle "help" as a positional command (alias for --help)
    if argv and argv[0] == "help":
        parser.print_help()
        return 0

    # Parse only the first argument to get the command
    parsed, remaining = parser.parse_known_args(argv)

    if not parsed.command:
        parser.print_help()
        return 0

    command = parsed.command
    args = remaining

    match command:
        case "assemble":
            from .commands.assemble import run

            return run(args)

        case "build":
            from .commands.build import run

            return run(args)

        case "create":
            from .commands.create import run

            return run(args)

        case "enter":
            from .commands.enter import run

            return run(args)

        case "ephemeral":
            from .commands.ephemeral import run

            return run(args)

        case "export":
            from .commands.export import run

            return run(args)

        case "generate-entry":
            from .commands.generate_entry import run

            return run(args)

        case "list" | "ls":
            from .commands.list import run

            return run(args)

        case "stop":
            from .commands.stop import run

            return run(args)

        case "rm":
            from .commands.rm import run

            return run(args)

        case "upgrade":
            from .commands.upgrade import run

            return run(args)

        case _:
            print_error(red("Error: invalid command"))
            parser.print_help(sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())
