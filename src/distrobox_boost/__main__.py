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
    profile     - Manage container configuration profiles
    ephemeral   - Runs with hijacking (intercepts internal create)

Passthrough commands (run with hijacking):
    enter, rm, stop, list, upgrade, generate-entry, assemble
"""

import sys

from distrobox_boost.command import profile
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
    "assemble",  # Intercept internal create calls
}


def print_help() -> None:
    """Print usage information."""
    print("""distrobox-boost - Shim for distrobox with automatic image optimization

Usage: distrobox-boost <command> [args...]

Commands:
  create [args...]                          Create container (auto-builds boost image)
  profile import --file <f> --name <n>      Import distrobox assemble config
  profile list                              List configured profiles
  profile rm <name>                         Remove a profile
  assemble [args...]                        Run distrobox assemble (with hijacking)
  ephemeral [args...]                       Run ephemeral (auto-optimizes create)

Passthrough (with hijacking):
  enter, rm, stop, list, upgrade, generate-entry

How it works:
  1. Import your distrobox config:
     distrobox-boost profile import --file mybox.ini --name mybox

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

    # Handle profile command (manage configuration profiles)
    if command == "profile":
        return profile.run_profile(rest)

    # Handle commands that need hijacking
    if command in HIJACKED_COMMANDS:
        return run_with_hooks(command, rest, use_hijack=True)

    # Unknown command - pass through to distrobox
    return run_passthrough(command, rest)


if __name__ == "__main__":
    sys.exit(main())
