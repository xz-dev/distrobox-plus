"""Image building logic for distrobox-boost.

Handles detection of when images need to be rebuilt and the actual
image building process.
"""

import subprocess

from distrobox_boost.utils.config import get_container_cache_dir, get_container_config_file
from distrobox_boost.utils.parsing import ContainerConfig, parse_config_without_header
from distrobox_boost.utils.templates import (
    generate_additional_packages_cmd,
    generate_hooks_cmd,
    generate_install_cmd,
    generate_upgrade_cmd,
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


def generate_containerfile(
    base_image: str,
    upgrade_cmd: str,
    install_cmd: str,
    pre_init_hooks_cmd: str,
    additional_packages_cmd: str,
    init_hooks_cmd: str,
) -> str:
    """Generate Containerfile with inline commands.

    Only includes steps where the corresponding command is non-empty.

    Args:
        base_image: Base image to build from.
        upgrade_cmd: Command to upgrade packages (always has value).
        install_cmd: Command to install distrobox deps (always has value).
        pre_init_hooks_cmd: Command for pre-init hooks (can be empty).
        additional_packages_cmd: Command to install extra packages (can be empty).
        init_hooks_cmd: Command for init hooks (can be empty).

    Returns:
        Containerfile content as string.
    """
    lines = [f"FROM {base_image}", ""]

    # 1. Upgrade all packages first (always included)
    lines.extend([
        "# Upgrade all packages",
        f"RUN {upgrade_cmd}",
        "",
    ])

    # 2. Pre-init hooks (only if has values)
    if pre_init_hooks_cmd:
        lines.extend([
            "# Pre-init hooks",
            f"RUN {pre_init_hooks_cmd}",
            "",
        ])

    # 3. Install distrobox dependencies (always included)
    lines.extend([
        "# Install distrobox dependencies",
        f"RUN {install_cmd}",
        "",
    ])

    # 4. Install additional_packages (only if has values)
    if additional_packages_cmd:
        lines.extend([
            "# Install additional packages",
            f"RUN {additional_packages_cmd}",
            "",
        ])

    # 5. Init hooks (only if has values)
    if init_hooks_cmd:
        lines.extend([
            "# Init hooks",
            f"RUN {init_hooks_cmd}",
            "",
        ])

    return "\n".join(lines)


def build_image(builder: str, name: str, containerfile_content: str) -> int:
    """Build container image using the specified builder.

    Reads Containerfile from stdin to avoid needing a build context directory.

    Args:
        builder: Image builder to use (buildah, podman, or docker).
        name: Name/tag for the resulting image.
        containerfile_content: Content of the Containerfile.

    Returns:
        Exit code from the build command.
    """
    if builder == "buildah":
        cmd = ["buildah", "bud", "-t", name, "-f", "-", "."]
    else:
        cmd = [builder, "build", "-t", name, "-f", "-", "."]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        input=containerfile_content,
        text=True,
        capture_output=True,
    )

    # Print stdout if any
    if result.stdout:
        print(result.stdout)

    # Print stderr on failure for debugging
    if result.returncode != 0 and result.stderr:
        print(f"Build error:\n{result.stderr}")

    return result.returncode


def has_config(name: str) -> bool:
    """Check if a config file exists for the given container.

    Args:
        name: Container name.

    Returns:
        True if a config file exists.
    """
    config_path = get_container_config_file(name)
    return config_path.exists()


def get_boost_image_name(name: str) -> str:
    """Get the boost image name for a container.

    Args:
        name: Container name.

    Returns:
        Image tag for the boost-optimized image.
    """
    return f"{name}:latest"


def image_exists(image_name: str) -> bool:
    """Check if a container image exists locally.

    Args:
        image_name: Full image name with tag.

    Returns:
        True if image exists.
    """
    builder = get_image_builder()
    if builder is None:
        return False

    if builder == "buildah":
        result = subprocess.run(
            ["buildah", "inspect", image_name],
            capture_output=True,
        )
    else:
        result = subprocess.run(
            [builder, "image", "inspect", image_name],
            capture_output=True,
        )

    return result.returncode == 0


def needs_rebuild(name: str) -> bool:
    """Check if an image needs to be rebuilt.

    Currently checks if:
    - Config exists AND
    - Image doesn't exist

    Future: Could compare config modification time with image creation time.

    Args:
        name: Container name.

    Returns:
        True if image should be rebuilt.
    """
    if not has_config(name):
        return False

    image_name = get_boost_image_name(name)
    return not image_exists(image_name)


def ensure_boost_image(name: str) -> int:
    """Build the boost image if needed.

    Args:
        name: Container name.

    Returns:
        0 on success, non-zero on failure.
    """
    config_path = get_container_config_file(name)
    if not config_path.exists():
        print(f"[distrobox-boost] No config found for '{name}', skipping build")
        return 0

    try:
        config: ContainerConfig = parse_config_without_header(config_path, name)
    except ValueError as e:
        print(f"[distrobox-boost] Error parsing config: {e}")
        return 1

    if not config.image:
        print(f"[distrobox-boost] No 'image' field found in config for '{name}'")
        return 1

    # Get image builder
    builder = get_image_builder()
    if builder is None:
        print("[distrobox-boost] Error: No image builder found (need buildah, podman, or docker)")
        return 1

    print(f"[distrobox-boost] Building optimized image for '{name}'...")
    print(f"[distrobox-boost] Using builder: {builder}")
    print(f"[distrobox-boost] Base image: {config.image}")

    # Generate inline commands
    upgrade_cmd = generate_upgrade_cmd()
    install_cmd = generate_install_cmd(DISTROBOX_PACKAGES)
    pre_init_hooks_cmd = generate_hooks_cmd(config.pre_init_hooks)
    additional_packages_cmd = generate_additional_packages_cmd(config.additional_packages)
    init_hooks_cmd = generate_hooks_cmd(config.init_hooks)

    # Generate Containerfile
    containerfile = generate_containerfile(
        config.image,
        upgrade_cmd=upgrade_cmd,
        install_cmd=install_cmd,
        pre_init_hooks_cmd=pre_init_hooks_cmd,
        additional_packages_cmd=additional_packages_cmd,
        init_hooks_cmd=init_hooks_cmd,
    )

    # Save Containerfile for debugging
    cache_dir = get_container_cache_dir(name)
    containerfile_path = cache_dir / "Containerfile"
    containerfile_path.write_text(containerfile, encoding="utf-8")

    # Build the image
    image_tag = get_boost_image_name(name)
    returncode = build_image(builder, image_tag, containerfile)

    if returncode != 0:
        print(f"[distrobox-boost] Failed to build image: {image_tag}")
        print(f"[distrobox-boost] Containerfile preserved at: {containerfile_path}")
        return returncode

    print(f"[distrobox-boost] Successfully built image: {image_tag}")
    return 0
