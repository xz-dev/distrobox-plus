"""distrobox-rm command implementation.

Removes one or more distrobox containers and cleans up exports.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import VERSION, Config, DEFAULT_NAME, check_sudo_doas, get_user_info
from ..container import detect_container_manager
from ..utils.console import print_msg, print_error, red
from ..utils.helpers import prompt_yes_no, InvalidInputError
from .list import list_containers

if TYPE_CHECKING:
    from ..container import ContainerManager


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-rm."""
    parser = argparse.ArgumentParser(
        prog="distrobox-rm",
        description="Remove distrobox containers",
    )
    parser.add_argument(
        "containers",
        nargs="*",
        help="Container name(s) to remove",
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Delete all distroboxes",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force deletion (implies --yes)",
    )
    parser.add_argument(
        "--rm-home",
        action="store_true",
        help="Remove the mounted home if it differs from host user's one",
    )
    parser.add_argument(
        "-Y", "--yes",
        action="store_true",
        help="Non-interactive, delete without asking",
    )
    parser.add_argument(
        "-r", "--root",
        action="store_true",
        help="Launch container manager with root privileges",
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


def get_all_distrobox_names(manager: ContainerManager) -> list[str]:
    """Get names of all distrobox containers.

    Args:
        manager: Container manager

    Returns:
        List of container names
    """
    containers = list_containers(manager)
    return [c["name"] for c in containers]


def cleanup_exported_binaries(container_name: str) -> None:
    """Remove exported binaries for a container.

    Args:
        container_name: Name of the container
    """
    bin_dir = Path.home() / ".local" / "bin"
    if not bin_dir.exists():
        return

    print_msg("Removing exported binaries...")

    for binary in bin_dir.iterdir():
        if not binary.is_file():
            continue

        try:
            content = binary.read_text()
            # Check if this binary was exported by distrobox for this container
            if "# distrobox_binary" in content and f"# name: {container_name}" in content:
                print_msg(f"Removing exported binary {binary}...")
                binary.unlink()
        except (OSError, UnicodeDecodeError):
            continue


def cleanup_exported_apps(container_name: str) -> None:
    """Remove exported desktop applications for a container.

    Args:
        container_name: Name of the container
    """
    apps_dir = Path.home() / ".local" / "share" / "applications"
    icons_dir = Path.home() / ".local" / "share" / "icons"

    if not apps_dir.exists():
        return

    # Find desktop files that match the container (original uses find with glob pattern)
    # Pattern: ${HOME}/.local/share/applications/${container_name}*
    pattern = f"{container_name}*"
    exec_pattern = re.compile(rf"Exec=.*{re.escape(container_name)} ")

    for desktop_file in apps_dir.glob(pattern):
        if not desktop_file.is_file() and not desktop_file.is_symlink():
            continue

        try:
            content = desktop_file.read_text()
            # Verify this is for our container using regex (matches original grep -le)
            if not exec_pattern.search(content):
                continue

            # Extract app name and icon (first occurrence only, like original head -n 1)
            app_name = None
            icon_name = None

            for line in content.splitlines():
                if line.startswith("Name=") and app_name is None:
                    app_name = line.split("=", 1)[1]
                elif line.startswith("Icon=") and icon_name is None:
                    icon_name = line.split("=", 1)[1]

            if app_name:
                print_msg(f"Removing exported app {app_name}...")

            desktop_file.unlink()

            # Remove associated icons
            if icon_name and icons_dir.exists():
                # Get basename of icon in case it's a full path
                icon_basename = Path(icon_name).stem
                if icon_basename:
                    for icon_file in icons_dir.rglob(f"{icon_basename}.*"):
                        icon_file.unlink()

        except (OSError, UnicodeDecodeError):
            continue


def run_generate_entry_delete(container_name: str, verbose: bool = False) -> None:
    """Run distrobox-generate-entry --delete for a container.

    Args:
        container_name: Name of the container
        verbose: Enable verbose output
    """
    from .generate_entry import run as generate_entry_run

    args = [container_name, "--delete"]
    if verbose:
        args.append("--verbose")

    try:
        generate_entry_run(args)
    except Exception:
        pass


def delete_container(
    manager: ContainerManager,
    name: str,
    force: bool = False,
    rm_home: bool = False,
    non_interactive: bool = False,
    verbose: bool = False,
) -> bool:
    """Delete a single container and clean up exports.

    Args:
        manager: Container manager
        name: Container name
        force: Force deletion
        rm_home: Remove custom home directory
        non_interactive: Skip prompts
        verbose: Enable verbose output

    Returns:
        True if successful
    """
    _, host_home, _ = get_user_info()

    # Check if container exists
    status = manager.get_status(name)
    if status is None:
        # Match original distrobox behavior: print warning but don't fail
        print_error(f"Cannot find container {name}.")
        return True

    # Get container's home directory
    container_home = manager.get_container_home(name)

    # If container has custom home, prompt for deletion
    # Original: only prompts if rm_home=1 AND non_interactive=0, default is "N"
    rm_home_local = False
    if container_home and container_home != host_home:
        if rm_home and not non_interactive:
            # InvalidInputError propagates to caller
            rm_home_local = prompt_yes_no(
                f"Do you want to remove custom home of container {name} ({container_home})?",
                default=False,
            )
        elif rm_home and non_interactive:
            # Original: if non_interactive, response_rm_home stays "N" (default)
            # so rm_home_local stays False
            rm_home_local = False

    # Remove the container
    print_msg("Removing container...")
    if not manager.rm(name, force=force, volumes=True):
        print_error(f"[error]Failed to remove container {name}[/error]")
        return False

    # Clean up exports
    cleanup_exported_binaries(name)
    cleanup_exported_apps(name)

    # Delete the desktop entry
    run_generate_entry_delete(name, verbose)

    # Remove custom home if requested
    if rm_home_local and container_home:
        try:
            shutil.rmtree(container_home)
            print_msg(f"Successfully removed {container_home}")
        except OSError as e:
            print_error(f"[error]Failed to remove {container_home}: {e}[/error]")

    return True


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-rm command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
        # Original uses basename and includes original args
        prog_name = Path(sys.argv[0]).name
        orig_args = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
        print_error(
            f"Running {prog_name} via SUDO/DOAS is not supported. "
            f"Instead, please try running:"
        )
        print_error(f"  {prog_name} --root {orig_args}")
        return 1

    # Parse arguments
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Load config
    config = Config.load()

    # Apply command line overrides
    if parsed.root:
        config.rootful = True
    if parsed.verbose:
        config.verbose = True
    if parsed.yes or parsed.force:
        config.non_interactive = True
    if parsed.rm_home:
        config.container_rm_custom_home = True

    force = parsed.force

    # Detect container manager
    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    # Determine which containers to remove
    container_names: list[str] = []

    if parsed.all:
        container_names = get_all_distrobox_names(manager)
        if not container_names:
            print_error("No containers found.")
            return 0
    elif parsed.containers:
        container_names = parsed.containers
    else:
        # Use default name
        container_names = [DEFAULT_NAME]

    # Prompt for confirmation
    names_str = " ".join(container_names)

    try:
        if not config.non_interactive and not force:
            if not prompt_yes_no(
                f"Do you really want to delete containers:{names_str}?",
                default=True,
            ):
                print_msg("Aborted.")
                return 0

        # Collect running containers first
        running_containers = [
            name for name in container_names
            if manager.is_running(name)
        ]

        # If there are running containers, ask once for all of them
        if running_containers and not config.non_interactive and not force:
            running_str = " ".join(running_containers)
            if prompt_yes_no(
                f"Containers {running_str} are running, do you want to force delete them?",
                default=True,
            ):
                force = True
            # If user refuses, continue without force flag - running containers will fail to delete

        # Delete containers
        for name in container_names:
            delete_container(
                manager,
                name,
                force=force,
                rm_home=config.container_rm_custom_home,
                non_interactive=config.non_interactive,
                verbose=config.verbose,
            )
    except InvalidInputError as e:
        print_error(f"[error]{e}[/error]")
        print_error("Exiting.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run())
