"""Template generation utilities."""


def generate_upgrade_script() -> str:
    """Generate a script to upgrade all packages in the base image.

    Based on distrobox-init upgrade logic.

    Returns:
        Shell script content as string.
    """
    return """#!/bin/sh
set -e

if command -v apk > /dev/null 2>&1; then
    apk update
    apk upgrade
elif command -v apt-get > /dev/null 2>&1; then
    apt-get update
    apt-get upgrade -o Dpkg::Options::="--force-confold" -y
elif command -v dnf > /dev/null 2>&1; then
    dnf upgrade -y
elif command -v microdnf > /dev/null 2>&1; then
    microdnf upgrade -y
elif command -v yum > /dev/null 2>&1; then
    yum upgrade -y
elif command -v pacman > /dev/null 2>&1; then
    pacman -Syyu --noconfirm
elif command -v zypper > /dev/null 2>&1; then
    zypper dup -y
else
    echo "Unsupported distribution"
    exit 1
fi
"""


def generate_install_script(packages: dict[str, list[str]]) -> str:
    """Generate a self-adaptive package installation script.

    The script detects the package manager available in the container
    and installs the appropriate packages. Based on distrobox-init logic.

    Note: This script assumes upgrade has already been run, so no update needed.

    Args:
        packages: Dict mapping package manager names to package lists.
                  Keys: apk, apt, dnf, pacman, zypper

    Returns:
        Shell script content as string.
    """
    return f"""#!/bin/sh
set -e

if command -v apk > /dev/null 2>&1; then
    apk add {" ".join(packages["apk"])}
elif command -v apt-get > /dev/null 2>&1; then
    apt-get install -y {" ".join(packages["apt"])}
elif command -v dnf > /dev/null 2>&1; then
    dnf install -y {" ".join(packages["dnf"])}
elif command -v microdnf > /dev/null 2>&1; then
    microdnf install -y {" ".join(packages["dnf"])}
elif command -v yum > /dev/null 2>&1; then
    yum install -y {" ".join(packages["dnf"])}
elif command -v pacman > /dev/null 2>&1; then
    pacman -S --noconfirm {" ".join(packages["pacman"])}
elif command -v zypper > /dev/null 2>&1; then
    zypper install -y {" ".join(packages["zypper"])}
else
    echo "Unsupported distribution"
    exit 1
fi
"""
