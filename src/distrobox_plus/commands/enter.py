"""distrobox-enter command implementation.

Enters a distrobox container.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import VERSION, Config, DEFAULT_IMAGE, DEFAULT_NAME, check_sudo_doas, get_user_info
from ..container import detect_container_manager
from ..utils import (
    prompt_yes_no,
    is_tty,
    get_cache_dir,
    filter_env_for_container,
    build_container_path,
    get_standard_paths,
    print_ok,
    print_err,
    print_status,
    green,
    yellow,
    red,
)

if TYPE_CHECKING:
    from ..container import ContainerManager


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-enter."""
    parser = argparse.ArgumentParser(
        prog="distrobox-enter",
        description="Enter a distrobox container",
    )
    parser.add_argument(
        "name_positional",
        nargs="?",
        help="Container name (positional)",
    )
    parser.add_argument(
        "-n", "--name",
        help=f"Name of the distrobox (default: {DEFAULT_NAME})",
    )
    parser.add_argument(
        "-e", "--exec",
        dest="exec_flag",
        action="store_true",
        help="Execute command (for compatibility)",
    )
    parser.add_argument(
        "--clean-path",
        action="store_true",
        help="Reset PATH to FHS standard",
    )
    parser.add_argument(
        "-T", "--no-tty",
        action="store_true",
        help="Don't allocate a TTY",
    )
    parser.add_argument(
        "-nw", "--no-workdir",
        action="store_true",
        help="Start from container's home directory",
    )
    parser.add_argument(
        "-a", "--additional-flags",
        action="append",
        default=[],
        help="Additional flags for container manager",
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Print command without executing",
    )
    parser.add_argument(
        "-Y", "--yes",
        action="store_true",
        help="Non-interactive mode",
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
        action="version",
        version=f"distrobox: {VERSION}",
    )

    return parser


def generate_enter_command(
    manager: ContainerManager,
    container_name: str,
    container_home: str,
    container_path: str,
    unshare_groups: bool,
    headless: bool,
    skip_workdir: bool,
    clean_path: bool,
    additional_flags: list[str],
) -> list[str]:
    """Generate the exec command for entering a container.

    Args:
        manager: Container manager
        container_name: Name of the container
        container_home: Container's HOME directory
        container_path: Container's PATH variable
        unshare_groups: Whether groups are unshared
        headless: Whether to skip TTY allocation
        skip_workdir: Start from container home instead of current dir
        clean_path: Use only standard FHS paths
        additional_flags: Additional flags for exec command

    Returns:
        List of command arguments
    """
    user, home, _ = get_user_info()
    distrobox_enter_path = shutil.which("distrobox-enter") or ""

    cmd = ["exec", "--interactive", "--detach-keys="]

    # User handling based on unshare_groups
    if unshare_groups:
        cmd.append("--user=root")
    else:
        cmd.append(f"--user={user}")

    # TTY allocation
    if not headless:
        cmd.append("--tty")

    # Working directory
    if skip_workdir:
        workdir = container_home
    else:
        cwd = os.getcwd()
        if container_home in cwd:
            workdir = cwd
        else:
            workdir = f"/run/host{cwd}"

    cmd.append(f"--workdir={workdir}")

    # Environment variables
    cmd.append(f"--env=PWD={workdir}")
    cmd.append(f"--env=CONTAINER_ID={container_name}")
    cmd.append(f"--env=DISTROBOX_ENTER_PATH={distrobox_enter_path}")

    # Forward filtered environment variables
    for key, value in filter_env_for_container().items():
        cmd.append(f"--env={key}={value}")

    # PATH handling
    path_value = build_container_path(os.environ.get("PATH", ""), clean_path)
    cmd.append(f"--env=PATH={path_value}")

    # XDG_DATA_DIRS
    xdg_data = os.environ.get("XDG_DATA_DIRS", "")
    standard_data = ["/usr/local/share", "/usr/share"]
    for path in standard_data:
        if path not in xdg_data:
            xdg_data = f"{xdg_data}:{path}" if xdg_data else path
    cmd.append(f"--env=XDG_DATA_DIRS={xdg_data}")

    # XDG directories relative to container home
    cmd.append(f"--env=XDG_CACHE_HOME={container_home}/.cache")
    cmd.append(f"--env=XDG_CONFIG_HOME={container_home}/.config")
    cmd.append(f"--env=XDG_DATA_HOME={container_home}/.local/share")
    cmd.append(f"--env=XDG_STATE_HOME={container_home}/.local/state")

    # XDG_CONFIG_DIRS
    xdg_config = os.environ.get("XDG_CONFIG_DIRS", "")
    if "/etc/xdg" not in xdg_config:
        xdg_config = f"{xdg_config}:/etc/xdg" if xdg_config else "/etc/xdg"
    cmd.append(f"--env=XDG_CONFIG_DIRS={xdg_config}")

    # Additional flags
    for flag in additional_flags:
        cmd.append(flag)

    # Container name
    cmd.append(container_name)

    return cmd


def wait_for_container_setup(
    manager: ContainerManager,
    container_name: str,
    verbose: bool = False,
) -> bool:
    """Wait for container setup to complete.

    Args:
        manager: Container manager
        container_name: Container name
        verbose: Enable verbose output

    Returns:
        True if setup completed successfully
    """
    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    fifo_path = cache_dir / f".{container_name}.fifo"

    # Clean up any existing fifo
    if fifo_path.exists():
        fifo_path.unlink()

    # Create named pipe
    os.mkfifo(fifo_path)

    try:
        # Get timestamp for log filtering
        log_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000000+00:00")

        print_status("Starting container...")

        while True:
            # Check container is still running
            status = manager.get_status(container_name)
            if status != "running":
                print("\nContainer Setup Failure!", file=sys.stderr)
                return False

            # Start logs process
            logs_cmd = [*manager._cmd_prefix, "logs", "--since", log_timestamp, "-f", container_name]
            logs_proc = subprocess.Popen(
                logs_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            try:
                for line in iter(logs_proc.stdout.readline, ""):  # type: ignore
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("+"):
                        # Logging command, ignore
                        continue
                    elif line.startswith("Error:"):
                        print(f"\n{red(line)}", file=sys.stderr)
                        logs_proc.kill()
                        return False
                    elif line.startswith("Warning:"):
                        print(f"\n{yellow(line)}", file=sys.stderr, end="")
                    elif line.startswith("distrobox:"):
                        msg = line.split(" ", 1)[1] if " " in line else line
                        print_ok()
                        print_status(msg)
                    elif line == "container_setup_done":
                        print_ok()
                        logs_proc.kill()
                        return True
            finally:
                logs_proc.kill()
                logs_proc.wait()

    finally:
        # Cleanup fifo
        if fifo_path.exists():
            fifo_path.unlink()


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-enter command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
        print(
            f"Running {sys.argv[0]} via SUDO/DOAS is not supported.",
            file=sys.stderr,
        )
        print(
            f"Instead, please try running:\n  {sys.argv[0]} --root",
            file=sys.stderr,
        )
        return 1

    if args is None:
        args = sys.argv[1:]

    # Split args at -- to separate distrobox args from container command
    container_command: list[str] = []
    distrobox_args = args

    if "--" in args:
        idx = args.index("--")
        distrobox_args = args[:idx]
        container_command = args[idx + 1:]
    elif "-e" in args:
        idx = args.index("-e")
        distrobox_args = args[:idx]
        container_command = args[idx + 1:]

    # Parse arguments
    parser = create_parser()
    parsed = parser.parse_args(distrobox_args)

    # Load config
    config = Config.load()

    # Apply command line overrides
    if parsed.root:
        config.rootful = True
    if parsed.verbose:
        config.verbose = True
    if parsed.yes:
        config.non_interactive = True
    if parsed.clean_path:
        config.clean_path = True
    if parsed.no_workdir:
        config.skip_workdir = True

    # Determine container name
    container_name = parsed.name or parsed.name_positional or config.container_name or DEFAULT_NAME

    # Determine if headless
    headless = parsed.no_tty or not is_tty()

    # Process additional flags
    additional_flags = []
    for flag in parsed.additional_flags:
        # Convert space-separated flags to proper format
        parts = flag.split()
        for part in parts:
            if part.startswith("--") and "=" not in part and len(parts) > 1:
                # This might be a --flag value pair
                idx = parts.index(part)
                if idx + 1 < len(parts) and not parts[idx + 1].startswith("--"):
                    additional_flags.append(f"{part}={parts[idx + 1]}")
                else:
                    additional_flags.append(part)
            else:
                additional_flags.append(part)

    # Detect container manager
    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    # Get container info
    user, home, _ = get_user_info()
    container_home = manager.get_container_home(container_name) or home
    container_path = manager.get_container_path(container_name) or os.environ.get("PATH", "")
    unshare_groups = manager.get_unshare_groups(container_name)

    # Check container status
    status = manager.get_status(container_name)

    # Dry run
    if parsed.dry_run:
        cmd = generate_enter_command(
            manager,
            container_name,
            container_home,
            container_path,
            unshare_groups,
            headless,
            config.skip_workdir,
            config.clean_path,
            additional_flags,
        )
        # Add command if specified
        if container_command:
            cmd.extend(container_command)
        else:
            cmd.extend(["/bin/sh", "-c", f"$(getent passwd '{user}' | cut -f 7 -d :) -l"])
        print(" ".join(cmd))
        return 0

    # Container doesn't exist - offer to create it
    if status is None:
        if not config.non_interactive:
            if not prompt_yes_no(f"Create it now, out of image {DEFAULT_IMAGE}?"):
                print("For creating it, run:", file=sys.stderr)
                print("\tdistrobox create <name> --image <image>", file=sys.stderr)
                return 0

        # Create the container
        create_cmd = ["distrobox-create", "--yes", "-i", DEFAULT_IMAGE, "-n", container_name]
        if config.rootful:
            create_cmd.insert(1, "--root")

        print(f"Creating container {container_name}...", file=sys.stderr)
        create_script = shutil.which("distrobox-create")
        if create_script:
            subprocess.run(create_cmd)
        else:
            # Use our own create command
            from .create import run as create_run
            create_args = ["--yes", "-i", DEFAULT_IMAGE, "-n", container_name]
            if config.rootful:
                create_args.insert(0, "--root")
            create_run(create_args)

        # Refresh status
        status = manager.get_status(container_name)

    # Start container if not running
    if status != "running":
        manager.start(container_name)

        # Wait for setup to complete
        if not wait_for_container_setup(manager, container_name, config.verbose):
            return 1

        print("\nContainer Setup Complete!", file=sys.stderr)

    # Generate and run enter command
    cmd = generate_enter_command(
        manager,
        container_name,
        container_home,
        container_path,
        unshare_groups,
        headless,
        config.skip_workdir,
        config.clean_path,
        additional_flags,
    )

    # Build the command to execute inside
    if container_command:
        # If single argument with spaces, execute via shell
        if len(container_command) == 1 and " " in container_command[0]:
            exec_cmd = ["/bin/sh", "-c", container_command[0]]
        else:
            exec_cmd = container_command
    else:
        # Default: run user's shell
        exec_cmd = ["/bin/sh", "-c", f"$(getent passwd '{user}' | cut -f 7 -d :) -l"]

    # Handle unshare_groups - need to use su
    if unshare_groups:
        su_cmd = ["su", user, "-m"]
        if not headless:
            su_cmd.append("--pty")
        su_cmd.extend(["-s", "/bin/sh", "-c", '"$0" "$@"', "--"])
        su_cmd.extend(exec_cmd)
        exec_cmd = su_cmd

    cmd.extend(exec_cmd)

    # Execute - replace current process
    manager.exec_replace(*cmd)

    # Should not reach here
    return 0


if __name__ == "__main__":
    sys.exit(run())
