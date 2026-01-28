"""distrobox-ephemeral command implementation.

Creates a temporary distrobox container that is automatically deleted on exit.
"""

from __future__ import annotations

import argparse
import secrets
import signal
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import VERSION, Config, check_sudo_doas, get_user_info

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType


@dataclass
class EphemeralOptions:
    """Options for ephemeral container."""

    name: str = ""
    container_command: list[str] = field(default_factory=list)
    create_flags: list[str] = field(default_factory=list)
    additional_flags: list[str] = field(default_factory=list)
    additional_packages: list[str] = field(default_factory=list)
    init_hooks: str = ""
    pre_init_hooks: str = ""


def generate_ephemeral_name() -> str:
    """Generate a random ephemeral container name.

    Matches original: mktemp -u distrobox-XXXXXXXXXX
    """
    chars = string.ascii_letters + string.digits  # [A-Za-z0-9] like mktemp
    suffix = "".join(secrets.choice(chars) for _ in range(10))
    return f"distrobox-{suffix}"


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-ephemeral."""
    user, _, _ = get_user_info()

    epilog = f"""\
This command also inherits all flags from distrobox-create.
Use -- or -e to pass commands to execute inside the container.

Examples:
    distrobox-ephemeral
    distrobox-ephemeral --image alpine:latest -- cat /etc/os-release
    distrobox-ephemeral --root --image fedora:39 -e bash
    distrobox-ephemeral --additional-packages "vim git" -- vim /tmp/test
"""

    parser = argparse.ArgumentParser(
        prog="distrobox-ephemeral",
        description=f"distrobox version: {VERSION}\n\n"
        "Create a temporary distrobox container that is automatically deleted on exit.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,  # We handle help ourselves to also show create options
    )
    parser.add_argument(
        "-h", "--help",
        action="store_true",
        help="show this help message and exit",
    )
    parser.add_argument(
        "-n", "--name",
        help="name for the ephemeral container (default: random)",
    )
    parser.add_argument(
        "-r", "--root",
        action="store_true",
        help="launch podman/docker/lilipod with root privileges",
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
    parser.add_argument(
        "-e", "--exec",
        dest="exec_delimiter",
        action="store_true",
        help=f"end arguments, execute the rest as command (default: {user}'s shell)",
    )
    # These are handled specially to be passed to create
    parser.add_argument(
        "-a", "--additional-flags",
        action="append",
        default=[],
        help="additional flags to pass to the container manager command",
    )
    parser.add_argument(
        "-ap", "--additional-packages",
        action="append",
        default=[],
        help="additional packages to install during initial container setup",
    )
    parser.add_argument(
        "--init-hooks",
        help="additional commands to execute at the end of container initialization",
    )
    parser.add_argument(
        "--pre-init-hooks",
        help="additional commands to execute at the start of container initialization",
    )

    return parser


def _print_sudo_error() -> int:
    """Print error message when running via sudo/doas."""
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


def _print_help(parser: argparse.ArgumentParser) -> None:
    """Print help message including inherited create options."""
    parser.print_help()
    print("\nInherited options from distrobox-create:")
    print("-" * 40)

    from .create import create_parser as create_create_parser

    create_parser_obj = create_create_parser()
    # Print only the options section from create help
    for action in create_parser_obj._actions:
        if action.option_strings and action.dest not in ("help", "version"):
            opts = ", ".join(action.option_strings)
            if action.help:
                print(f"  {opts:<30} {action.help}")


def _split_args(args: list[str]) -> tuple[list[str], list[str]]:
    """Split args at -- or -e to separate ephemeral args from container command.

    Returns:
        Tuple of (ephemeral_args, container_command)
    """
    for i, arg in enumerate(args):
        if arg in ("--", "-e", "--exec"):
            return args[:i], args[i + 1:]
    return args, []


def _apply_cli_overrides(config: Config, parsed: argparse.Namespace) -> None:
    """Apply command line overrides to config."""
    if parsed.root:
        config.rootful = True
    if parsed.verbose:
        config.verbose = True


def _build_ephemeral_options(
    parsed: argparse.Namespace,
    create_flags: list[str],
    container_command: list[str],
) -> EphemeralOptions:
    """Build EphemeralOptions from parsed arguments.

    Args:
        parsed: Parsed arguments
        create_flags: Unknown arguments to pass to create
        container_command: Command to run in container

    Returns:
        EphemeralOptions instance
    """
    return EphemeralOptions(
        name=parsed.name or generate_ephemeral_name(),
        container_command=container_command,
        create_flags=create_flags,
        additional_flags=parsed.additional_flags,
        additional_packages=parsed.additional_packages,
        init_hooks=parsed.init_hooks or "",
        pre_init_hooks=parsed.pre_init_hooks or "",
    )


def _build_extra_flags(config: Config) -> list[str]:
    """Build extra flags from config (--verbose, --root)."""
    extra_flags: list[str] = []
    if config.verbose:
        extra_flags.append("--verbose")
    if config.rootful:
        extra_flags.append("--root")
    return extra_flags


def _build_create_args(opts: EphemeralOptions, extra_flags: list[str]) -> list[str]:
    """Build create command arguments.

    Args:
        opts: Ephemeral options
        extra_flags: Extra flags (--verbose, --root)

    Returns:
        List of arguments for create command
    """
    create_args: list[str] = []

    # Add additional flags (combine into single argument like original)
    if opts.additional_flags:
        combined_flags = " ".join(opts.additional_flags)
        create_args.extend(["--additional-flags", combined_flags])

    # Add additional packages (combine into single argument like original)
    if opts.additional_packages:
        combined_packages = " ".join(opts.additional_packages)
        create_args.extend(["--additional-packages", combined_packages])

    # Add init hooks (default to space like original shell script)
    init_hooks = opts.init_hooks if opts.init_hooks else " "
    create_args.extend(["--init-hooks", init_hooks])

    # Add pre-init hooks (default to space like original shell script)
    pre_init_hooks = opts.pre_init_hooks if opts.pre_init_hooks else " "
    create_args.extend(["--pre-init-hooks", pre_init_hooks])

    # Add extra flags, create flags, and final options
    create_args.extend(extra_flags)
    create_args.extend(opts.create_flags)
    create_args.extend(["--yes", "--name", opts.name])

    return create_args


def _build_enter_args(opts: EphemeralOptions, extra_flags: list[str]) -> list[str]:
    """Build enter command arguments.

    Args:
        opts: Ephemeral options
        extra_flags: Extra flags (--verbose, --root)

    Returns:
        List of arguments for enter command
    """
    enter_args: list[str] = [*extra_flags, opts.name]
    if opts.container_command:
        enter_args.append("--")
        enter_args.extend(opts.container_command)
    return enter_args


def _build_rm_args(name: str, extra_flags: list[str]) -> list[str]:
    """Build rm command arguments.

    Args:
        name: Container name
        extra_flags: Extra flags (--verbose, --root)

    Returns:
        List of arguments for rm command
    """
    return [*extra_flags, "--force", name, "--yes"]


def _create_cleanup_handler(
    name: str,
    extra_flags: list[str],
) -> tuple[Callable[..., None], Callable[[], None]]:
    """Create cleanup handler and signal setup function.

    Args:
        name: Container name
        extra_flags: Extra flags (--verbose, --root)

    Returns:
        Tuple of (cleanup_func, setup_signals_func)
    """
    def cleanup(signum: int | None = None, frame: FrameType | None = None) -> None:
        """Clean up the ephemeral container."""
        # Reset signal handlers
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGHUP, signal.SIG_DFL)

        # Run rm
        from .rm import run as rm_run

        rm_args = _build_rm_args(name, extra_flags)
        rm_run(rm_args)

    def setup_signals() -> None:
        """Set up signal handlers for cleanup."""
        signal.signal(signal.SIGTERM, cleanup)
        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGHUP, cleanup)

    return cleanup, setup_signals


def _execute_ephemeral(opts: EphemeralOptions, extra_flags: list[str]) -> int:
    """Execute ephemeral container workflow: create, enter, cleanup.

    Args:
        opts: Ephemeral options
        extra_flags: Extra flags (--verbose, --root)

    Returns:
        Exit code
    """
    cleanup, setup_signals = _create_cleanup_handler(opts.name, extra_flags)
    setup_signals()

    # Run create
    from .create import run as create_run

    create_args = _build_create_args(opts, extra_flags)
    create_result = create_run(create_args)

    if create_result != 0:
        cleanup()
        return create_result

    # Run enter
    from .enter import run as enter_run

    enter_args = _build_enter_args(opts, extra_flags)
    exit_code = enter_run(enter_args)

    # Clean up
    cleanup()

    return exit_code


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-ephemeral command.

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

    # Split args at delimiter
    ephemeral_args, container_command = _split_args(args)

    # Parse known arguments, collect unknown ones as create flags
    parser = create_parser()
    parsed, create_flags = parser.parse_known_args(ephemeral_args)

    # Handle help
    if parsed.help:
        _print_help(parser)
        return 0

    # Load config and apply overrides
    config = Config.load()
    _apply_cli_overrides(config, parsed)

    # Build options
    opts = _build_ephemeral_options(parsed, create_flags, container_command)
    extra_flags = _build_extra_flags(config)

    return _execute_ephemeral(opts, extra_flags)


if __name__ == "__main__":
    sys.exit(run())
