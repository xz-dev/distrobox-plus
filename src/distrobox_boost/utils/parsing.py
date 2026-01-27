"""Shared parsing utilities for distrobox config files.

This module contains common parsing logic used by both assemble.py and builder.py
to avoid code duplication.
"""

import configparser
from dataclasses import dataclass, field
from pathlib import Path

# Fields that are baked into the optimized image
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


def parse_multiline_value(value: str) -> list[str]:
    """Parse a multiline or space-separated value into a list.

    Handles both:
    - Space-separated: "git curl wget"
    - Multiline with quotes: "first command" "second command"
    - Escaped quotes within quoted strings: "echo \\"hello\\""

    Args:
        value: Raw value string from INI file.

    Returns:
        List of individual items.

    Raises:
        ValueError: If quotes are unbalanced.
    """
    if not value or not value.strip():
        return []

    # Check if it contains quoted strings (multiline hooks style)
    if '"' in value:
        items = []
        current = ""
        in_quotes = False
        i = 0
        while i < len(value):
            char = value[i]

            # Handle escape sequences inside quotes
            if in_quotes and char == "\\" and i + 1 < len(value):
                next_char = value[i + 1]
                if next_char in ('"', "\\"):
                    current += next_char
                    i += 2
                    continue

            if char == '"':
                in_quotes = not in_quotes
                if not in_quotes and current.strip():
                    items.append(current.strip())
                    current = ""
            elif in_quotes:
                current += char
            i += 1

        # Check for unbalanced quotes
        if in_quotes:
            raise ValueError(f"Unbalanced quotes in value: {value}")

        return items

    # Simple space-separated list
    return value.split()


def _parse_config_section(
    section: configparser.SectionProxy,
    container_name: str,
) -> ContainerConfig:
    """Parse a config section into ContainerConfig.

    Args:
        section: ConfigParser section proxy.
        container_name: Name of the container.

    Returns:
        Parsed container configuration.
    """
    result = ContainerConfig(name=container_name)
    result.image = section.get("image", "").strip()
    result.additional_packages = parse_multiline_value(
        section.get("additional_packages", "")
    )
    result.pre_init_hooks = parse_multiline_value(section.get("pre_init_hooks", ""))
    result.init_hooks = parse_multiline_value(section.get("init_hooks", ""))

    # Collect remaining options (not baked into image)
    for key, value in section.items():
        if key not in BAKED_FIELDS:
            result.remaining_options[key] = [value] if value else []

    return result


def parse_config_with_header(file_path: Path, container_name: str) -> ContainerConfig:
    """Parse INI file that has a section header.

    Used for parsing original distrobox assemble files.

    Args:
        file_path: Path to the INI file with section headers.
        container_name: Name of the container section to extract.

    Returns:
        Parsed container configuration.

    Raises:
        ValueError: If container section not found or file can't be parsed.
    """
    if not file_path.exists():
        raise ValueError(f"Config file not found: {file_path}")

    config = configparser.ConfigParser()
    config.optionxform = str  # type: ignore[assignment]
    config.read(file_path, encoding="utf-8")

    if container_name not in config.sections():
        raise ValueError(
            f"Container '{container_name}' not found in {file_path}. "
            f"Available sections: {config.sections()}"
        )

    return _parse_config_section(config[container_name], container_name)


def parse_config_without_header(
    file_path: Path, container_name: str
) -> ContainerConfig:
    """Parse config file without section header.

    Used for parsing distrobox-boost stored config files where the container
    name is determined by the directory structure.

    Args:
        file_path: Path to the config file (no section headers).
        container_name: Name of the container (from directory structure).

    Returns:
        Parsed container configuration.

    Raises:
        ValueError: If file not found or can't be parsed.
    """
    if not file_path.exists():
        raise ValueError(f"Config file not found: {file_path}")

    # Read file and temporarily add section header for configparser
    content = file_path.read_text(encoding="utf-8")
    temp_content = f"[{container_name}]\n{content}"

    config = configparser.ConfigParser()
    config.optionxform = str  # type: ignore[assignment]
    config.read_string(temp_content)

    return _parse_config_section(config[container_name], container_name)
