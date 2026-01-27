"""Profile command: manage container configuration profiles.

The profile command supports:
- import: Import original assemble config into distrobox-boost
- list: List all configured container profiles
- rm: Remove a container profile
"""

import shutil
from pathlib import Path

from distrobox_boost.utils.config import get_config_dir, get_container_config_dir, get_container_config_file
from distrobox_boost.utils.parsing import ContainerConfig, parse_config_with_header


def write_config_without_header(path: Path, config: ContainerConfig) -> None:
    """Write config file without section header.

    The container name is determined by the directory structure, not the file content.

    Args:
        path: Path to write the config file.
        config: Container configuration to write.
    """
    lines = []
    if config.image:
        lines.append(f"image={config.image}")
    if config.additional_packages:
        lines.append(f"additional_packages={' '.join(config.additional_packages)}")
    if config.pre_init_hooks:
        # Wrap each hook in quotes, escape any internal quotes
        hooks = " ".join(
            f'"{h.replace(chr(92), chr(92)+chr(92)).replace(chr(34), chr(92)+chr(34))}"'
            for h in config.pre_init_hooks
        )
        lines.append(f"pre_init_hooks={hooks}")
    if config.init_hooks:
        hooks = " ".join(
            f'"{h.replace(chr(92), chr(92)+chr(92)).replace(chr(34), chr(92)+chr(34))}"'
            for h in config.init_hooks
        )
        lines.append(f"init_hooks={hooks}")
    for key, values in config.remaining_options.items():
        for value in values:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def handle_import(args: list[str]) -> int:
    """Handle 'profile import' command.

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
        print("Usage: distrobox-boost profile import --file <file> --name <name>")
        return 1

    source_path = Path(file_path)
    if not source_path.exists():
        print(f"Error: File not found: {file_path}")
        return 1

    # Parse original file and extract the specified section
    try:
        config = parse_config_with_header(source_path, name)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    # Write config without section header
    dest_path = get_container_config_file(name)
    write_config_without_header(dest_path, config)

    print(f"Imported config for '{name}' to: {dest_path}")
    print("The optimized image will be built automatically on first create.")
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
