"""CLI entry point for distrobox-boost.

distrobox-boost acts as a shim for distrobox, intercepting commands to
apply optimizations while passing others through with PATH hijacking.

Flow:
    User: distrobox-boost ephemeral --image alpine
              ↓
    [ephemeral runs with hijacking]
              ↓
    ephemeral internally calls distrobox-create
              ↓
    [hijacked → distrobox-boost create]
              ↓
    [create pre-hook: detect config → build image → replace args]
              ↓
    [real distrobox-create runs with optimized image]

Usage:
    distrobox-boost <command> [args...]

Commands that get special handling:
    create      - Auto-builds optimized images, replaces --image
    assemble    - Supports 'import' subcommand, runs with hijacking
    ephemeral   - Runs with hijacking (intercepts internal create)

Passthrough commands (run with hijacking):
    enter, rm, stop, list, upgrade, generate-entry
"""

import sys

from distrobox_boost.command import assemble
from distrobox_boost.command.create import run_create
from distrobox_boost.command.wrapper import run_passthrough, run_with_hooks

# Commands that need hijacking (they call other distrobox commands internally)
HIJACKED_COMMANDS = {
    "ephemeral",  # Calls create, enter, rm
    "enter",
    "rm",
    "stop",
    "list",
    "upgrade",
    "generate-entry",
}


def print_help() -> None:
    """Print usage information."""
    print("""distrobox-boost - Shim for distrobox with automatic image optimization

Usage: distrobox-boost <command> [args...]

Commands:
  create [args...]                         Create container (auto-builds boost image)
  assemble import --file <f> --name <n>    Import distrobox assemble config
  assemble [args...]                       Run distrobox assemble (with hijacking)
  ephemeral [args...]                      Run ephemeral (auto-optimizes create)

Passthrough (with hijacking):
  enter, rm, stop, list, upgrade, generate-entry

How it works:
  1. Import your distrobox config:
     distrobox-boost assemble import --file mybox.ini --name mybox

  2. Create containers (image is built automatically on first run):
     distrobox-boost create --name mybox --image archlinux:latest
     # or
     distrobox-boost assemble create --file mybox.ini

  3. Use ephemeral (internal create is automatically optimized):
     distrobox-boost ephemeral --image alpine:latest --name mybox

The optimized image is built once and reused for all subsequent creates.
""")


def main() -> int:
    """Main CLI entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print_help()
        return 0

    command = args[0]
    rest = args[1:]

    # Handle create command (special: has pre-hook for auto-build)
    if command == "create":
        return run_create(rest)

    # Handle assemble command (special: supports import subcommand)
    if command == "assemble":
        return handle_assemble(rest)

    # Handle commands that need hijacking
    if command in HIJACKED_COMMANDS:
        return run_with_hooks(command, rest, use_hijack=True)

    # Unknown command - pass through to distrobox
    return run_passthrough(command, rest)


def handle_assemble(args: list[str]) -> int:
    """Handle assemble subcommands.

    Args:
        args: Arguments after 'assemble'.

    Returns:
        Exit code.
    """
    if not args:
        print("Usage: distrobox-boost assemble <subcommand|args...>")
        print("Subcommands: import")
        print("Or: distrobox-boost assemble [distrobox-assemble-args...]")
        return 1

    subcommand = args[0]

    # assemble import --file <f> --name <n>
    if subcommand == "import":
        return handle_assemble_import(args[1:])

    # Pass through to distrobox-assemble with hijacking
    return assemble.run_assemble(args)


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
