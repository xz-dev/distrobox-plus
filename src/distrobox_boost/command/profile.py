"""Profile command: manage container configuration profiles.

The profile command supports:
- import: Import original assemble config into distrobox-boost (splits multi-container files)
- list: List all configured container profiles
- rm: Remove a container profile
"""

import configparser
import shutil
from pathlib import Path

from distrobox_boost.utils.config import (
    get_config_dir,
    get_container_config_dir,
    get_container_config_file,
)


def handle_import(args: list[str]) -> int:
    """Handle 'profile import' command.

    Imports a distrobox assemble config file. If the file contains multiple
    container sections, each is split into its own directory using the
    section header (container name) as the directory name.

    Args:
        args: Arguments after 'import'. Expects --file <path>.

    Returns:
        Exit code.
    """
    file_path = None

    i = 0
    while i < len(args):
        if args[i] == "--file" and i + 1 < len(args):
            file_path = args[i + 1]
            i += 2
        else:
            i += 1

    if not file_path:
        print("Usage: distrobox-boost profile import --file <file>")
        return 1

    source_path = Path(file_path)
    if not source_path.exists():
        print(f"Error: File not found: {file_path}")
        return 1

    # Parse the config file to get all container sections
    config = configparser.ConfigParser()
    config.optionxform = str  # type: ignore[assignment]
    config.read(source_path, encoding="utf-8")

    sections = config.sections()
    if not sections:
        print(f"Error: No container sections found in {file_path}")
        return 1

    # Import each container section into its own directory
    for container_name in sections:
        dest_path = get_container_config_file(container_name)

        # Write section content without header (directory name is the container name)
        lines = []
        for key, value in config[container_name].items():
            lines.append(f"{key}={value}")

        dest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Imported '{container_name}' to: {dest_path}")

    print(f"\nImported {len(sections)} container(s). Optimized images will be built on first create.")
    return 0


def handle_list() -> int:
    """Handle 'profile list' command.

    Lists all configured container profiles with their config file paths.

    Returns:
        Exit code.
    """
    config_dir = get_config_dir()

    if not config_dir.exists():
        print("No profiles configured.")
        return 0

    profiles = []
    for item in sorted(config_dir.iterdir()):
        if item.is_dir():
            config_file = item / "distrobox.ini"
            if config_file.exists():
                profiles.append((item.name, config_file))

    if not profiles:
        print("No profiles configured.")
        return 0

    for name, config_file in profiles:
        print(f"{name}: {config_file}")

    return 0


def handle_rm(args: list[str]) -> int:
    """Handle 'profile rm' command.

    Removes a container profile configuration directory.

    Args:
        args: Arguments after 'rm' (should contain profile name).

    Returns:
        Exit code.
    """
    if not args:
        print("Usage: distrobox-boost profile rm <name>")
        return 1

    name = args[0]
    config_dir = get_container_config_dir(name)

    if not config_dir.exists():
        print(f"Error: Profile '{name}' not found.")
        return 1

    shutil.rmtree(config_dir)
    print(f"Removed profile '{name}'.")
    return 0


def run_profile(args: list[str]) -> int:
    """Run profile subcommand.

    Routes to appropriate handler based on subcommand.

    Args:
        args: Arguments after 'profile'.

    Returns:
        Exit code.
    """
    if not args:
        print("Usage: distrobox-boost profile <subcommand>")
        print("Subcommands: import, list, rm")
        return 1

    subcommand = args[0]
    rest = args[1:]

    if subcommand == "import":
        return handle_import(rest)
    elif subcommand == "list":
        return handle_list()
    elif subcommand == "rm":
        return handle_rm(rest)
    else:
        print(f"Unknown subcommand: {subcommand}")
        print("Subcommands: import, list, rm")
        return 1
