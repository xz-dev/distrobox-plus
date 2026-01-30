"""Builder utilities for pre-built distrobox images.

Creates Containerfiles with distrobox dependencies pre-installed,
allowing for faster container startup by caching the build layer.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from .console import print_error, print_msg
from .templates import (
    generate_additional_packages_cmd,
    generate_hooks_cmd,
    generate_install_cmd,
    generate_upgrade_cmd,
)

if TYPE_CHECKING:
    from ..container import ContainerManager


def get_boost_image_name(name: str) -> str:
    """Get the name for a boosted image.

    Args:
        name: Base container name

    Returns:
        Image tag with distrobox-plus suffix
    """
    # Sanitize name to be a valid image tag
    safe_name = name.lower().replace("/", "-").replace(":", "-")
    return f"{safe_name}:distrobox-plus"


def get_boost_image_tag(
    base_image: str,
    additional_packages: str = "",
    init_hooks: str = "",
    pre_init_hooks: str = "",
) -> str:
    """Generate a unique image tag based on inputs.

    Creates a hash-based tag to enable caching of different configurations.

    Args:
        base_image: Base image name
        additional_packages: Space-separated additional packages
        init_hooks: Init hooks command
        pre_init_hooks: Pre-init hooks command

    Returns:
        Unique image tag
    """
    # Create a hash of the configuration
    content = f"{base_image}|{additional_packages}|{init_hooks}|{pre_init_hooks}"
    config_hash = hashlib.sha256(content.encode()).hexdigest()[:12]

    # Sanitize base image name
    safe_name = base_image.lower().replace("/", "-").replace(":", "-")
    return f"{safe_name}-boost:{config_hash}"


def generate_containerfile(
    base_image: str,
    additional_packages: str = "",
    init_hooks: str = "",
    pre_init_hooks: str = "",
) -> str:
    """Generate Containerfile content for a boosted image.

    Args:
        base_image: Base image to build from
        additional_packages: Space-separated additional packages to install
        init_hooks: Commands to run at end of init
        pre_init_hooks: Commands to run at start of init

    Returns:
        Containerfile content as string
    """
    lines = [
        f"FROM {base_image}",
        "",
        "# Marker for boosted image - distrobox-init will skip package setup",
        "RUN touch /.distrobox-boost",
        "",
    ]

    # Add upgrade command
    upgrade_cmd = generate_upgrade_cmd()
    lines.extend(
        [
            "# Upgrade existing packages",
            f"RUN {upgrade_cmd}",
            "",
        ]
    )

    # Add pre-init hooks if specified
    if pre_init_hooks:
        hooks_cmd = generate_hooks_cmd(pre_init_hooks)
        lines.extend(
            [
                "# Pre-init hooks",
                f"RUN {hooks_cmd}",
                "",
            ]
        )

    # Add distrobox package installation
    install_cmd = generate_install_cmd()
    lines.extend(
        [
            "# Install distrobox dependencies (conditional per-package check)",
            f"RUN {install_cmd}",
            "",
        ]
    )

    # Add additional packages if specified
    if additional_packages:
        additional_cmd = generate_additional_packages_cmd(additional_packages)
        lines.extend(
            [
                "# Install additional packages",
                f"RUN {additional_cmd}",
                "",
            ]
        )

    # Add init hooks if specified
    if init_hooks:
        hooks_cmd = generate_hooks_cmd(init_hooks)
        lines.extend(
            [
                "# Init hooks",
                f"RUN {hooks_cmd}",
                "",
            ]
        )

    return "\n".join(lines)


def build_image(
    manager: ContainerManager,
    tag: str,
    containerfile_content: str,
    verbose: bool = False,
) -> bool:
    """Build a container image from Containerfile content.

    Uses stdin to pass the Containerfile to avoid temp files.

    Args:
        manager: Container manager to use
        tag: Image tag to build
        containerfile_content: Containerfile content
        verbose: Show build output

    Returns:
        True if build succeeded
    """
    import subprocess

    cmd = [*manager.cmd_prefix, "build", "-t", tag, "-f", "-", "."]

    if verbose:
        print_msg(f"Building image {tag}...")
        print_msg("Containerfile:")
        print_msg(containerfile_content)

    result = subprocess.run(
        cmd,
        input=containerfile_content,
        text=True,
        capture_output=not verbose,
    )

    return result.returncode == 0


def image_exists(manager: ContainerManager, image_name: str) -> bool:
    """Check if an image exists locally.

    Args:
        manager: Container manager
        image_name: Image name to check

    Returns:
        True if image exists
    """
    return manager.image_exists(image_name)


def ensure_boost_image(
    manager: ContainerManager,
    base_image: str,
    additional_packages: str = "",
    init_hooks: str = "",
    pre_init_hooks: str = "",
    verbose: bool = False,
    force: bool = False,
) -> str | None:
    """Ensure a boosted image exists, building if needed.

    Args:
        manager: Container manager
        base_image: Base image to build from
        additional_packages: Additional packages to install
        init_hooks: Init hooks command
        pre_init_hooks: Pre-init hooks command
        verbose: Show verbose output
        force: Force rebuild even if image exists

    Returns:
        Image tag if successful, None on failure
    """
    tag = get_boost_image_tag(base_image, additional_packages, init_hooks, pre_init_hooks)

    # Check if image already exists
    if not force and image_exists(manager, tag):
        if verbose:
            print_msg(f"Using existing boosted image: {tag}")
        return tag

    # Generate and build the Containerfile
    containerfile = generate_containerfile(
        base_image,
        additional_packages,
        init_hooks,
        pre_init_hooks,
    )

    print_error(f"Building boosted image: {tag}")

    if build_image(manager, tag, containerfile, verbose):
        print_error(f"Successfully built: {tag}")
        return tag
    else:
        print_error(f"Failed to build boosted image: {tag}")
        return None
