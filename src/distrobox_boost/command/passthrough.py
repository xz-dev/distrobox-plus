"""Passthrough commands: forward unmodified to distrobox."""

import subprocess


def run_passthrough(command: str, args: list[str]) -> int:
    """Pass a command through to distrobox unchanged.

    Args:
        command: The distrobox subcommand (e.g., "enter", "rm", "list").
        args: Additional arguments to pass to the command.

    Returns:
        Exit code from distrobox.
    """
    cmd = ["distrobox", command, *args]
    result = subprocess.run(cmd)
    return result.returncode
