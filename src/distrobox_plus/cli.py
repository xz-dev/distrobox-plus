"""Command-line interface router for distrobox-plus.

Routes commands to the appropriate subcommand handlers.
"""

from __future__ import annotations

import sys

from .config import VERSION

HELP_TEXT = f"""\
distrobox version: {VERSION}

Choose one of the available commands:
    create
    enter
    ephemeral
    list | ls
    rm
    stop
    version
    help
"""


def show_help() -> None:
    """Print help message."""
    print(HELP_TEXT)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for distrobox-plus CLI.

    Routes commands to the appropriate subcommand handlers.

    Args:
        argv: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        show_help()
        return 0

    command = argv[0]
    args = argv[1:]

    match command:
        case "create":
            from .commands.create import run
            return run(args)

        case "enter":
            from .commands.enter import run
            return run(args)

        case "ephemeral":
            from .commands.ephemeral import run
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

        case "-V" | "--version" | "version":
            print(f"distrobox: {VERSION}")
            return 0

        case "-h" | "--help" | "help":
            show_help()
            return 0

        case _:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            print(file=sys.stderr)
            show_help()
            return 1


if __name__ == "__main__":
    sys.exit(main())
