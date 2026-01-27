"""Assemble command: import configs and run distrobox assemble with hijacking.

The assemble command supports:
- import: Import original assemble config into distrobox-boost
- Passthrough: Run distrobox-assemble with hijacking to intercept create calls
"""

from pathlib import Path

from distrobox_boost.command.wrapper import run_with_hooks
from distrobox_boost.utils.config import get_container_config_file
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


def run_import(file: str, name: str) -> int:
    """Import original assemble file into config directory.

    Parses the original file (which has a section header) and saves
    only the key=value pairs without the section header. The container
    name is determined by the directory structure.

    Args:
        file: Path to original assemble file.
        name: Container name (section name in the INI file).

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    source_path = Path(file)
    if not source_path.exists():
        print(f"Error: File not found: {file}")
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
    print(f"The optimized image will be built automatically on first create.")
    return 0


def run_assemble(args: list[str]) -> int:
    """Run distrobox assemble with hijacking.

    Passes through to the real distrobox-assemble, but with PATH hijacking
    enabled so that any internal create calls will be intercepted.

    Args:
        args: Arguments to pass to distrobox-assemble.

    Returns:
        Exit code from distrobox assemble.
    """
    return run_with_hooks(
        "assemble",
        args,
        use_hijack=True,  # Intercept internal create calls
    )
