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
    jinja_env,
)

if TYPE_CHECKING:
    from ..container import ContainerManager

# Containerfile template - stages are conditionally included
_CONTAINERFILE_TEMPLATE = jinja_env.from_string("""\
FROM {{ base_image }} AS init

# Marker for boosted image - distrobox-init will skip package setup
RUN touch /.distrobox-boost

# Upgrade existing packages
RUN {{ upgrade_cmd }}

# Install distrobox dependencies (conditional per-package check)
RUN {{ install_cmd }}

{% for stage in stages %}
FROM {{ stage.from }} AS {{ stage.name }}

# {{ stage.comment }}
RUN {{ stage.run }}

{% endfor %}
""")


def get_boost_image_name(name: str) -> str:
    """Get the name for a boosted image."""
    safe_name = name.lower().replace("/", "-").replace(":", "-")
    return f"{safe_name}:distrobox-plus"


def get_boost_image_tag(
    base_image: str,
    additional_packages: str = "",
    init_hooks: str = "",
    pre_init_hooks: str = "",
) -> str:
    """Generate a unique image tag based on inputs."""
    content = f"{base_image}|{additional_packages}|{init_hooks}|{pre_init_hooks}"
    config_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    safe_name = base_image.lower().replace("/", "-").replace(":", "-")
    return f"{safe_name}-boost:{config_hash}"


def generate_containerfile(
    base_image: str,
    additional_packages: str = "",
    init_hooks: str = "",
    pre_init_hooks: str = "",
) -> str:
    """Generate multi-stage Containerfile content for a boosted image.

    Creates a multi-stage build with conditional stages that chain together.
    """
    # Build stages list dynamically - each stage depends on the previous
    stages: list[dict[str, str]] = []
    prev_stage = "init"

    if pre_init_hooks:
        stages.append(
            {
                "from": prev_stage,
                "name": "pre-hooks",
                "comment": "Pre-init hooks",
                "run": generate_hooks_cmd(pre_init_hooks),
            }
        )
        prev_stage = "pre-hooks"

    if additional_packages:
        stages.append(
            {
                "from": prev_stage,
                "name": "packages",
                "comment": "Install additional packages",
                "run": generate_additional_packages_cmd(additional_packages),
            }
        )
        prev_stage = "packages"

    if init_hooks:
        stages.append(
            {
                "from": prev_stage,
                "name": "runner",
                "comment": "Init hooks",
                "run": generate_hooks_cmd(init_hooks),
            }
        )

    return _CONTAINERFILE_TEMPLATE.render(
        base_image=base_image,
        upgrade_cmd=generate_upgrade_cmd(),
        install_cmd=generate_install_cmd(),
        stages=stages,
    )


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
    tag = get_boost_image_tag(
        base_image, additional_packages, init_hooks, pre_init_hooks
    )

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
