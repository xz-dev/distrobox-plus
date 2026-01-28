"""distrobox-ephemeral command implementation.

Creates a temporary distrobox container that is automatically deleted on exit.
"""

from __future__ import annotations

import argparse
import secrets
import signal
import string
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import VERSION, Config, check_sudo_doas

if TYPE_CHECKING:
    from types import FrameType


def generate_ephemeral_name() -> str:
    """Generate a random ephemeral container name.

    Matches original: mktemp -u distrobox-XXXXXXXXXX
    """
    chars = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(10))
    return f"distrobox-{suffix}"


def show_help() -> None:
    """Print help message."""
    help_text = f"""\
distrobox version: {VERSION}

Usage:

\tdistrobox-ephemeral [--root/-r]

Options:

\t--root/-r:\t\tlaunch podman/docker/lilipod with root privileges. Note that if you need root this is the preferred
\t\t\t\tway over "sudo distrobox" (note: if using a program other than 'sudo' for root privileges is necessary,
\t\t\t\tspecify it through the DBX_SUDO_PROGRAM env variable, or 'distrobox_sudo_program' config variable)
\t--verbose/-v:\t\tshow more verbosity
\t--help/-h:\t\tshow this message
\t--/-e:\t\t\tend arguments execute the rest as command to execute at login\tdefault: default user's shell
\t--version/-V:\t\tshow version

See also:

\tdistrobox-ephemeral also inherits all the flags from distrobox-create:
"""
    print(help_text)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-ephemeral."""
    parser = argparse.ArgumentParser(
        prog="distrobox-ephemeral",
        description="Create a temporary distrobox container",
        add_help=False,  # We handle help ourselves to match original format
    )
    parser.add_argument(
        "-h", "--help",
        action="store_true",
        help="Show help message",
    )
    parser.add_argument(
        "-n", "--name",
        help="Name for the ephemeral container (default: random)",
    )
    parser.add_argument(
        "-r", "--root",
        action="store_true",
        help="Launch with root privileges",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show more verbosity",
    )
    parser.add_argument(
        "-V", "--version",
        action="store_true",
        help="Show version",
    )
    # These are handled specially to be passed to create
    parser.add_argument(
        "-a", "--additional-flags",
        action="append",
        default=[],
        help="Additional flags for container manager",
    )
    parser.add_argument(
        "-ap", "--additional-packages",
        action="append",
        default=[],
        help="Additional packages to install",
    )
    parser.add_argument(
        "--init-hooks",
        help="Commands to execute at end of container init",
    )
    parser.add_argument(
        "--pre-init-hooks",
        help="Commands to execute at start of container init",
    )

    return parser


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-ephemeral command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
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

    if args is None:
        args = sys.argv[1:]

    # Split args at -- or -e to separate ephemeral args from container command
    container_command: list[str] = []
    ephemeral_args = args
    create_flags: list[str] = []

    # Find -- or -e delimiter
    delimiter_idx = -1
    for i, arg in enumerate(args):
        if arg in ("--", "-e", "--exec"):
            delimiter_idx = i
            break

    if delimiter_idx >= 0:
        ephemeral_args = args[:delimiter_idx]
        container_command = args[delimiter_idx + 1:]

    # Parse known arguments, collect unknown ones as create flags
    parser = create_parser()
    parsed, unknown = parser.parse_known_args(ephemeral_args)
    create_flags = unknown

    # Handle help
    if parsed.help:
        show_help()
        # Also show create help
        from .create import create_parser as create_create_parser
        create_help = create_create_parser()
        # Print create help without the first line (usage)
        import io
        help_io = io.StringIO()
        create_help.print_help(help_io)
        help_text = help_io.getvalue()
        # Skip first line (usage)
        lines = help_text.split("\n", 1)
        if len(lines) > 1:
            print(lines[1])
        return 0

    # Handle version
    if parsed.version:
        print(f"distrobox: {VERSION}")
        return 0

    # Load config
    config = Config.load()

    # Apply command line overrides
    if parsed.root:
        config.rootful = True
    if parsed.verbose:
        config.verbose = True

    # Generate container name
    container_name = parsed.name or generate_ephemeral_name()

    # Build extra flags
    extra_flags: list[str] = []
    if config.verbose:
        extra_flags.append("--verbose")
    if config.rootful:
        extra_flags.append("--root")

    # Build create command arguments
    create_args: list[str] = []

    # Add additional flags
    for flag in parsed.additional_flags:
        create_args.extend(["--additional-flags", flag])

    # Add additional packages
    for pkg in parsed.additional_packages:
        create_args.extend(["--additional-packages", pkg])

    # Add init hooks
    if parsed.init_hooks:
        create_args.extend(["--init-hooks", parsed.init_hooks])

    # Add pre-init hooks
    if parsed.pre_init_hooks:
        create_args.extend(["--pre-init-hooks", parsed.pre_init_hooks])

    # Add extra flags, create flags, and final options
    create_args.extend(extra_flags)
    create_args.extend(create_flags)
    create_args.extend(["--yes", "--name", container_name])

    # Cleanup function
    def cleanup(signum: int | None = None, frame: FrameType | None = None) -> None:
        """Clean up the ephemeral container."""
        # Reset signal handlers
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGHUP, signal.SIG_DFL)

        # Build rm args
        rm_args = [*extra_flags, "--force", container_name, "--yes"]

        # Run rm
        from .rm import run as rm_run
        rm_run(rm_args)

    # Set up signal handlers
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGHUP, cleanup)

    # Run create
    from .create import run as create_run
    create_result = create_run(create_args)

    if create_result != 0:
        cleanup()
        return create_result

    # Build enter command arguments
    enter_args: list[str] = [*extra_flags, container_name]
    if container_command:
        enter_args.append("--")
        enter_args.extend(container_command)

    # Run enter
    from .enter import run as enter_run
    exit_code = enter_run(enter_args)

    # Clean up
    cleanup()

    return exit_code


if __name__ == "__main__":
    sys.exit(run())
