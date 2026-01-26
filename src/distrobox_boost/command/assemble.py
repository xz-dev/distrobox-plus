"""Assemble commands: import, rebuild, and assemble distrobox containers."""

import configparser
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from distrobox_boost.utils.config import get_container_cache_dir, get_container_config_file
from distrobox_boost.utils.templates import (
    generate_additional_packages_script,
    generate_hooks_script,
    generate_install_script,
    generate_upgrade_script,
)
from distrobox_boost.utils.utils import get_image_builder

# Package lists for distrobox dependencies by package manager
# Based on distrobox requirements for full functionality
DISTROBOX_PACKAGES: dict[str, list[str]] = {
    "apk": [
        "bash",
        "bc",
        "bzip2",
        "curl",
        "diffutils",
        "findutils",
        "gnupg",
        "gpg",
        "less",
        "lsof",
        "mount",
        "ncurses",
        "ncurses-terminfo",
        "pinentry",
        "procps",
        "shadow",
        "sudo",
        "tar",
        "tree",
        "tzdata",
        "umount",
        "util-linux",
        "util-linux-misc",
        "vte3",
        "wget",
        "xz",
        "zip",
    ],
    "apt": [
        "apt-utils",
        "bash",
        "bc",
        "bzip2",
        "curl",
        "diffutils",
        "findutils",
        "gnupg2",
        "less",
        "libnss-myhostname",
        "libvte-2.91-common",
        "libvte-common",
        "lsof",
        "ncurses-base",
        "passwd",
        "pinentry-curses",
        "procps",
        "sudo",
        "tar",
        "time",
        "tree",
        "tzdata",
        "util-linux",
        "wget",
        "xz-utils",
        "zip",
    ],
    "dnf": [
        "bash",
        "bc",
        "bzip2",
        "curl",
        "diffutils",
        "dnf-plugins-core",
        "findutils",
        "gnupg2",
        "less",
        "lsof",
        "ncurses",
        "passwd",
        "pinentry",
        "procps-ng",
        "shadow-utils",
        "sudo",
        "tar",
        "time",
        "tree",
        "tzdata",
        "util-linux",
        "vte-profile",
        "wget",
        "xz",
        "zip",
    ],
    "pacman": [
        "bash",
        "bc",
        "bzip2",
        "curl",
        "diffutils",
        "findutils",
        "gnupg",
        "less",
        "lsof",
        "ncurses",
        "pinentry",
        "procps-ng",
        "shadow",
        "sudo",
        "tar",
        "time",
        "tree",
        "tzdata",
        "util-linux",
        "vte-common",
        "wget",
        "xz",
        "zip",
    ],
    "zypper": [
        "bash",
        "bc",
        "bzip2",
        "curl",
        "diffutils",
        "findutils",
        "gpg2",
        "less",
        "lsof",
        "ncurses",
        "pinentry",
        "procps",
        "shadow",
        "sudo",
        "tar",
        "time",
        "tree",
        "timezone",
        "util-linux",
        "wget",
        "xz",
        "zip",
    ],
}


def build_image(builder: str, name: str, containerfile_path: str, context_path: str) -> int:
    """Build container image using the specified builder.

    Args:
        builder: Image builder to use (buildah, podman, or docker).
        name: Name/tag for the resulting image.
        containerfile_path: Path to the Containerfile.
        context_path: Build context directory path.

    Returns:
        Exit code from the build command.
    """
    if builder == "buildah":
        cmd = ["buildah", "bud", "-t", name, "-f", containerfile_path, context_path]
    else:
        cmd = [builder, "build", "-t", name, "-f", containerfile_path, context_path]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode


# Fields that are baked into the image (removed from optimized config)
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


def generate_assemble_content(config: ContainerConfig, new_image: str) -> str:
    """Generate optimized INI content (no baked fields, local image).

    Args:
        config: Parsed container configuration.
        new_image: New image name to use (the built optimized image).

    Returns:
        INI file content as string.
    """
    lines = [f"[{config.name}]", f"image={new_image}"]

    # Add remaining options (not baked into image)
    for key, values in config.remaining_options.items():
        for value in values:
            lines.append(f"{key}={value}")

    return "\n".join(lines) + "\n"


def generate_containerfile(
    base_image: str,
    has_pre_hooks: bool,
    has_packages: bool,
    has_hooks: bool,
) -> str:
    """Generate Containerfile with conditional steps.

    Only includes steps where the corresponding field has non-empty values.

    Args:
        base_image: Base image to build from.
        has_pre_hooks: Whether pre_init_hooks has values.
        has_packages: Whether additional_packages has values.
        has_hooks: Whether init_hooks has values.

    Returns:
        Containerfile content as string.
    """
    lines = [f"FROM {base_image}", ""]

    # 1. Upgrade all packages first (always included)
    lines.extend([
        "# Upgrade all packages",
        "COPY upgrade.sh /tmp/upgrade.sh",
        "RUN chmod +x /tmp/upgrade.sh && /tmp/upgrade.sh && rm /tmp/upgrade.sh",
        "",
    ])

    # 2. Pre-init hooks (only if has values)
    if has_pre_hooks:
        lines.extend([
            "# Pre-init hooks",
            "COPY pre_init_hooks.sh /tmp/pre_init_hooks.sh",
            "RUN chmod +x /tmp/pre_init_hooks.sh && /tmp/pre_init_hooks.sh && rm /tmp/pre_init_hooks.sh",
            "",
        ])

    # 3. Install distrobox dependencies (always included)
    lines.extend([
        "# Install distrobox dependencies",
        "COPY install.sh /tmp/install.sh",
        "RUN chmod +x /tmp/install.sh && /tmp/install.sh && rm /tmp/install.sh",
        "",
    ])

    # 4. Install additional_packages (only if has values)
    if has_packages:
        lines.extend([
            "# Install additional packages",
            "COPY additional_packages.sh /tmp/additional_packages.sh",
            "RUN chmod +x /tmp/additional_packages.sh && /tmp/additional_packages.sh && rm /tmp/additional_packages.sh",
            "",
        ])

    # 5. Init hooks (only if has values)
    if has_hooks:
        lines.extend([
            "# Init hooks",
            "COPY init_hooks.sh /tmp/init_hooks.sh",
            "RUN chmod +x /tmp/init_hooks.sh && /tmp/init_hooks.sh && rm /tmp/init_hooks.sh",
            "",
        ])

    return "\n".join(lines)


def run_import(file: str, name: str) -> int:
    """Import original assemble file into config directory.

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

    # Validate that the container section exists
    try:
        parse_assemble_file(source_path, name)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    # Copy to config directory
    dest_path = get_container_config_file(name)
    shutil.copy(source_path, dest_path)

    print(f"Imported config for '{name}' to: {dest_path}")
    return 0


def run_rebuild(name: str) -> int:
    """Build optimized image and generate new assemble file.

    Args:
        name: Container name to rebuild.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Read original config
    config_path = get_container_config_file(name)
    if not config_path.exists():
        print(f"Error: No config found for '{name}'. Run 'distrobox-boost assemble import' first.")
        print(f"Expected: {config_path}")
        return 1

    try:
        config = parse_assemble_file(config_path, name)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    if not config.image:
        print(f"Error: No 'image' field found in config for '{name}'")
        return 1

    # Get image builder
    builder = get_image_builder()
    if builder is None:
        print("Error: No image builder found. Please install buildah, podman, or docker.")
        return 1

    print(f"Using image builder: {builder}")
    print(f"Rebuilding '{name}' from base '{config.image}'...")

    # Prepare cache directory
    cache_dir = get_container_cache_dir(name)

    # Generate and write scripts
    upgrade_path = cache_dir / "upgrade.sh"
    upgrade_path.write_text(generate_upgrade_script())

    install_path = cache_dir / "install.sh"
    install_path.write_text(generate_install_script(DISTROBOX_PACKAGES))

    # Conditional scripts
    has_pre_hooks = bool(config.pre_init_hooks)
    has_packages = bool(config.additional_packages)
    has_hooks = bool(config.init_hooks)

    if has_pre_hooks:
        pre_hooks_path = cache_dir / "pre_init_hooks.sh"
        pre_hooks_path.write_text(generate_hooks_script(config.pre_init_hooks))

    if has_packages:
        packages_path = cache_dir / "additional_packages.sh"
        packages_path.write_text(generate_additional_packages_script(config.additional_packages))

    if has_hooks:
        hooks_path = cache_dir / "init_hooks.sh"
        hooks_path.write_text(generate_hooks_script(config.init_hooks))

    # Generate and write Containerfile
    containerfile = generate_containerfile(
        config.image,
        has_pre_hooks=has_pre_hooks,
        has_packages=has_packages,
        has_hooks=has_hooks,
    )
    containerfile_path = cache_dir / "Containerfile"
    containerfile_path.write_text(containerfile)

    # Build the image
    image_tag = f"{name}:latest"
    returncode = build_image(builder, image_tag, str(containerfile_path), str(cache_dir))

    if returncode != 0:
        print(f"Failed to build image: {image_tag}")
        print(f"Build files preserved at: {cache_dir}")
        return returncode

    print(f"Successfully built image: {image_tag}")

    # Generate optimized assemble file in cache
    optimized_content = generate_assemble_content(config, image_tag)
    optimized_path = cache_dir / "distrobox.ini"
    optimized_path.write_text(optimized_content)

    print(f"Generated optimized config: {optimized_path}")
    return 0


def run_assemble(name: str, passthrough_args: list[str]) -> int:
    """Run distrobox assemble with optimized config.

    Passes through all arguments to distrobox assemble, only adding --file.

    Args:
        name: Container name (used to find the optimized config).
        passthrough_args: Arguments to pass through to distrobox assemble
                          (e.g., ["create", "--dry-run"] or ["rm"]).

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    cache_dir = get_container_cache_dir(name)
    config_path = cache_dir / "distrobox.ini"

    if not config_path.exists():
        print(f"Error: No optimized config found for '{name}'. Run 'distrobox-boost rebuild' first.")
        print(f"Expected: {config_path}")
        return 1

    # Build command: distrobox assemble <passthrough_args> --file <config_path>
    cmd = ["distrobox", "assemble", *passthrough_args, "--file", str(config_path)]
    print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd)
    return result.returncode
