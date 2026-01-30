"""distrobox-build command implementation.

Builds optimized container images with distrobox dependencies pre-installed.
"""

from __future__ import annotations

import argparse
import sys

from ..config import VERSION, Config, check_sudo_doas
from ..container import detect_container_manager
from ..utils.builder import ensure_boost_image, get_boost_image_tag
from ..utils.console import green, print_error, red


def build_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-build."""
    epilog = """\
Examples:
    distrobox build --image alpine:latest
    distrobox build --image fedora:40 --additional-packages "git vim"
    distrobox build --image ubuntu:22.04 --init-hooks "touch /var/tmp/marker"
    distrobox build --image archlinux:latest --pre-init-hooks "pacman-key --init"

The build command creates a locally-cached container image with distrobox
dependencies pre-installed. This significantly speeds up container creation
and first-run startup time.

Built images are tagged with a hash of their configuration, enabling automatic
caching - the same configuration will reuse an existing build.
"""

    parser = argparse.ArgumentParser(
        prog="distrobox-build",
        description="Build an optimized container image with distrobox dependencies pre-installed",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--image",
        required=True,
        help="base image to build from (required)",
    )
    parser.add_argument(
        "-ap",
        "--additional-packages",
        action="append",
        default=[],
        help="additional packages to install in the image",
    )
    parser.add_argument(
        "--init-hooks",
        help="commands to execute at the end of image setup",
    )
    parser.add_argument(
        "--pre-init-hooks",
        help="commands to execute at the start of image setup",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force rebuild even if image already exists",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="only print the Containerfile without building",
    )
    parser.add_argument(
        "-r",
        "--root",
        action="store_true",
        help="use root privileges for building",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show more verbosity",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"distrobox: {VERSION}",
    )

    return parser


def _print_sudo_error() -> int:
    """Print error message when running via sudo/doas."""
    print_error(f"Running {sys.argv[0]} via SUDO/DOAS is not supported.")
    print_error(f"Instead, please try running:\n  {sys.argv[0]} --root")
    return 1


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-build command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    if check_sudo_doas():
        return _print_sudo_error()

    parser = build_parser()
    parsed = parser.parse_args(args)

    config = Config.load()

    # Apply CLI overrides
    if parsed.root:
        config.rootful = True
    if parsed.verbose:
        config.verbose = True

    # Get container manager
    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    # Prepare options
    image = parsed.image
    additional_packages = " ".join(parsed.additional_packages)
    init_hooks = parsed.init_hooks or ""
    pre_init_hooks = parsed.pre_init_hooks or ""

    # Dry run - show Containerfile
    if parsed.dry_run:
        from ..utils.builder import generate_containerfile

        containerfile = generate_containerfile(
            image,
            additional_packages,
            init_hooks,
            pre_init_hooks,
        )
        print("# Generated Containerfile:")
        print(containerfile)
        tag = get_boost_image_tag(image, additional_packages, init_hooks, pre_init_hooks)
        print(f"# Would be tagged as: {tag}")
        return 0

    # Check if base image exists, pull if not
    if not manager.image_exists(image):
        print_error(f"Pulling base image: {image}")
        if not manager.pull(image):
            print_error(red(f"Failed to pull image: {image}"))
            return 1

    # Build the image
    result = ensure_boost_image(
        manager,
        image,
        additional_packages,
        init_hooks,
        pre_init_hooks,
        verbose=config.verbose,
        force=parsed.force,
    )

    if result:
        print_error(green(f"Built image: {result}"))
        print_error("\nTo use this image, run:")
        print_error(f"  distrobox create --image {result} --name <container-name>")
        return 0
    else:
        print_error(red("Build failed"))
        return 1


if __name__ == "__main__":
    sys.exit(run())
