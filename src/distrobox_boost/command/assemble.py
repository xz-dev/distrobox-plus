"""Assemble command: import configs and run distrobox assemble with hijacking.

The assemble command supports:
- import: Import original assemble config into distrobox-boost
- Passthrough: Run distrobox-assemble with hijacking to intercept create calls
"""

import configparser
from dataclasses import dataclass, field
from pathlib import Path

from distrobox_boost.command.wrapper import run_with_hooks
from distrobox_boost.utils.config import get_container_config_file

# Fields that are baked into the image (kept for reference in config parsing)
BAKED_FIELDS = {"image", "additional_packages", "pre_init_hooks", "init_hooks"}


@dataclass
class ContainerConfig:
    """Parsed container configuration."""

    name: str
    image: str = ""
    additional_packages: list[str] = field(default_factory=list)
    pre_init_hooks: list[str] = field(default_factory=list)
    init_hooks: list[str] = field(default_factory=list)
    remaining_options: dict[str, list[str]] = field(default_factory=dict)


def _parse_multiline_value(value: str) -> list[str]:
    """Parse a multiline or space-separated value into a list.

    Handles both:
    - Space-separated: "git curl wget"
    - Multiline with quotes: "first command" "second command"

    Args:
        value: Raw value string from INI file.

    Returns:
        List of individual items.
    """
    if not value or not value.strip():
        return []

    # Check if it contains quoted strings (multiline hooks style)
    if '"' in value:
        items = []
        current = ""
        in_quotes = False
        for char in value:
            if char == '"':
                in_quotes = not in_quotes
                if not in_quotes and current.strip():
                    items.append(current.strip())
                    current = ""
            elif in_quotes:
                current += char
        return items

    # Simple space-separated list
    return value.split()


def parse_assemble_file(file_path: Path, container_name: str) -> ContainerConfig:
    """Parse INI file and extract the specified container's config.

    Args:
        file_path: Path to the assemble INI file.
        container_name: Name of the container section to extract.

    Returns:
        Parsed container configuration.

    Raises:
        ValueError: If container section not found or file can't be parsed.
    """
    if not file_path.exists():
        raise ValueError(f"Assemble file not found: {file_path}")

    config = configparser.ConfigParser()
    # Preserve case of keys
    config.optionxform = str  # type: ignore[assignment]
    config.read(file_path)

    if container_name not in config.sections():
        raise ValueError(
            f"Container '{container_name}' not found in {file_path}. "
            f"Available sections: {config.sections()}"
        )

    section = config[container_name]

    # Parse fields
    result = ContainerConfig(name=container_name)
    result.image = section.get("image", "").strip()
    result.additional_packages = _parse_multiline_value(section.get("additional_packages", ""))
    result.pre_init_hooks = _parse_multiline_value(section.get("pre_init_hooks", ""))
    result.init_hooks = _parse_multiline_value(section.get("init_hooks", ""))

    # Collect remaining options (not baked into image)
    for key, value in section.items():
        if key not in BAKED_FIELDS:
            result.remaining_options[key] = [value] if value else []

    return result


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
        # Wrap each hook in quotes
        hooks = " ".join(f'"{h}"' for h in config.pre_init_hooks)
        lines.append(f"pre_init_hooks={hooks}")
    if config.init_hooks:
        hooks = " ".join(f'"{h}"' for h in config.init_hooks)
        lines.append(f"init_hooks={hooks}")
    for key, values in config.remaining_options.items():
        for value in values:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n")


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
        config = parse_assemble_file(source_path, name)
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
