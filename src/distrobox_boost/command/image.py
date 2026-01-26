"""Image command: build distrobox-ready container images."""

import subprocess
import sys
from pathlib import Path

from distrobox_boost.utils.config import get_container_cache_dir
from distrobox_boost.utils.templates import generate_install_script, generate_upgrade_script
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


def generate_containerfile(base_image: str) -> str:
    """Generate Containerfile content.

    Args:
        base_image: Base image to build from.

    Returns:
        Containerfile content as string.
    """
    return f"""FROM {base_image}

COPY upgrade.sh /tmp/upgrade.sh
RUN chmod +x /tmp/upgrade.sh && /tmp/upgrade.sh && rm /tmp/upgrade.sh

COPY install.sh /tmp/install.sh
RUN chmod +x /tmp/install.sh && /tmp/install.sh && rm /tmp/install.sh
"""


def run(name: str, base: str) -> int:
    """Build a distrobox-ready container image.

    Args:
        name: Name/tag for the resulting image.
        base: Base image to build from.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    builder = get_image_builder()
    if builder is None:
        print("Error: No image builder found. Please install buildah, podman, or docker.")
        return 1

    print(f"Using image builder: {builder}")
    print(f"Building image '{name}' from base '{base}'...")

    # Use cache directory for build context (preserved for debugging on failure)
    cache_dir = get_container_cache_dir(name)

    # Generate and write upgrade script
    upgrade_script = generate_upgrade_script()
    upgrade_path = cache_dir / "upgrade.sh"
    upgrade_path.write_text(upgrade_script)

    # Generate and write install script
    install_script = generate_install_script(DISTROBOX_PACKAGES)
    install_path = cache_dir / "install.sh"
    install_path.write_text(install_script)

    # Generate and write Containerfile
    containerfile = generate_containerfile(base)
    containerfile_path = cache_dir / "Containerfile"
    containerfile_path.write_text(containerfile)

    # Build the image
    returncode = build_image(builder, name, str(containerfile_path), str(cache_dir))

    if returncode == 0:
        print(f"Successfully built image: {name}")
    else:
        print(f"Failed to build image: {name}")
        print(f"Build files preserved at: {cache_dir}")

    return returncode


if __name__ == "__main__":
    # Allow running directly for testing
    if len(sys.argv) < 3:
        print("Usage: python -m distrobox_boost.command.image <name> <base>")
        sys.exit(1)
    sys.exit(run(sys.argv[1], sys.argv[2]))
