"""CLI entry point for distrobox-boost.

distrobox-boost acts as a wrapper around distrobox, intercepting specific
commands to apply optimizations while passing others through unchanged.

Usage:
    distrobox-boost <command> [args...]

Special commands:
    assemble import --file <f> --name <n>   Import original config
    assemble rebuild <name>                  Build optimized image
    assemble <name> <args...>                Run assemble with hijacking
    create [args...]                         Create with image replacement

Passthrough commands:
    enter, rm, list, stop, upgrade, ephemeral, generate-entry -> distrobox
"""

import sys

from distrobox_boost.command import assemble
from distrobox_boost.command.create import run_create
from distrobox_boost.command.passthrough import run_passthrough

# Commands that pass through to distrobox unchanged
PASSTHROUGH_COMMANDS = {
    "enter",
    "rm",
    "list",
    "stop",
    "upgrade",
    "ephemeral",
    "generate-entry",
}


def print_help() -> None:
    """Print usage information."""
    print("""distrobox-boost - Enhanced distrobox workflow

Usage: distrobox-boost <command> [args...]

Commands:
  assemble import --file <f> --name <n>   Import original assemble config
  assemble rebuild <name>                  Build optimized image from config
  assemble <name> <args...>                Run distrobox assemble with hijacking
  create [args...]                         Create container (with boost image if available)

Passthrough (forwarded to distrobox):
  enter, rm, list, stop, upgrade, ephemeral, generate-entry

Examples:
  distrobox-boost assemble import --file mybox.ini --name mybox
  distrobox-boost assemble rebuild mybox
  distrobox-boost assemble mybox create
  distrobox-boost list
""")


def main() -> int:
    """Main CLI entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print_help()
        return 0

    command = args[0]
    rest = args[1:]

    # Handle assemble subcommands
    if command == "assemble":
        return handle_assemble(rest)

    # Handle create command (intercepted)
    if command == "create":
        return run_create(rest)

    # Handle passthrough commands
    if command in PASSTHROUGH_COMMANDS:
        return run_passthrough(command, rest)

    # Unknown command
    print(f"Unknown command: {command}")
    print("Run 'distrobox-boost --help' for usage.")
    return 1


def handle_assemble(args: list[str]) -> int:
    """Handle assemble subcommands.

    Args:
        args: Arguments after 'assemble'.

    Returns:
        Exit code.
    """
    if not args:
        print("Usage: distrobox-boost assemble <subcommand|name> [args...]")
        print("Subcommands: import, rebuild")
        print("Or: distrobox-boost assemble <name> <distrobox-assemble-args>")
        return 1

    subcommand = args[0]

    # assemble import --file <f> --name <n>
    if subcommand == "import":
        return handle_assemble_import(args[1:])

    # assemble rebuild <name>
    if subcommand == "rebuild":
        if len(args) < 2:
            print("Usage: distrobox-boost assemble rebuild <name>")
            return 1
        return assemble.run_rebuild(args[1])

    # assemble <name> <args...> - run with hijacking
    name = subcommand
    passthrough = args[1:] if len(args) > 1 else []
    return assemble.run_assemble(name, passthrough)


def handle_assemble_import(args: list[str]) -> int:
    """Handle 'assemble import' command.

    Args:
        args: Arguments after 'import'.

    Returns:
        Exit code.
    """
    file_path = None
    name = None

    i = 0
    while i < len(args):
        if args[i] == "--file" and i + 1 < len(args):
            file_path = args[i + 1]
            i += 2
        elif args[i] == "--name" and i + 1 < len(args):
            name = args[i + 1]
            i += 2
        else:
            i += 1

    if not file_path or not name:
        print("Usage: distrobox-boost assemble import --file <file> --name <name>")
        return 1

    return assemble.run_import(file_path, name)


if __name__ == "__main__":
    sys.exit(main())
