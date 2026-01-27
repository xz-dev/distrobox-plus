"""Generic command wrapper framework with pre/post hooks.

Provides a unified way to run distrobox commands in a hijacked environment,
optionally applying pre and post hooks to modify arguments or handle results.
"""

import shutil
import subprocess
from collections.abc import Callable

from distrobox_boost.utils.hijack import HijackManager

# Type aliases for hook functions
PreHook = Callable[[list[str]], list[str] | None]
PostHook = Callable[[subprocess.CompletedProcess[bytes | str]], None]


def run_with_hooks(
    command: str,
    args: list[str],
    *,
    pre_hook: PreHook | None = None,
    post_hook: PostHook | None = None,
    use_hijack: bool = True,
) -> int:
    """Run a distrobox command with optional pre/post hooks.

    This is the core wrapper that all distrobox-boost commands use. It:
    1. Runs the pre-hook (which can modify arguments)
    2. Executes the real distrobox command (optionally in hijack environment)
    3. Runs the post-hook (for cleanup or logging)

    Args:
        command: The distrobox command to run (e.g., "create", "ephemeral").
        args: Arguments to pass to the command.
        pre_hook: Optional function to run before the command.
                  Receives args list, returns modified args or None to use original.
        post_hook: Optional function to run after the command.
                   Receives the CompletedProcess result.
        use_hijack: If True, run in hijack environment (intercept internal calls).
                    If False, run directly without hijacking.

    Returns:
        Exit code from the distrobox command.
    """
    # 1. Run pre-hook to potentially modify arguments
    if pre_hook is not None:
        modified_args = pre_hook(args)
        if modified_args is not None:
            args = modified_args

    # 2. Find the real distrobox command
    real_cmd = shutil.which(f"distrobox-{command}")
    if real_cmd is None:
        # Fall back to 'distrobox <command>'
        real_distrobox = shutil.which("distrobox")
        if real_distrobox is None:
            print(f"Error: distrobox-{command} not found in PATH")
            return 1
        cmd = [real_distrobox, command, *args]
    else:
        cmd = [real_cmd, *args]

    # 3. Execute the command (with or without hijacking)
    if use_hijack:
        with HijackManager() as hijack:
            result = subprocess.run(cmd, env=hijack.env)
    else:
        result = subprocess.run(cmd)

    # 4. Run post-hook
    if post_hook is not None:
        post_hook(result)

    return result.returncode


def run_passthrough(command: str, args: list[str]) -> int:
    """Pass a command through to distrobox unchanged.

    No hijacking, no hooks - just forward to the real distrobox command.

    Args:
        command: The distrobox subcommand (e.g., "enter", "rm", "list").
        args: Additional arguments to pass to the command.

    Returns:
        Exit code from distrobox.
    """
    real_cmd = shutil.which(f"distrobox-{command}")
    if real_cmd is None:
        real_distrobox = shutil.which("distrobox")
        if real_distrobox is None:
            print(f"Error: distrobox not found in PATH")
            return 1
        cmd = [real_distrobox, command, *args]
    else:
        cmd = [real_cmd, *args]

    result = subprocess.run(cmd)
    return result.returncode
