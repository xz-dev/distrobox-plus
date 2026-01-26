"""Template generation utilities for inline Containerfile commands."""


def generate_hooks_cmd(hooks: list[str]) -> str:
    """Generate an inline command to run hook commands.

    Args:
        hooks: List of shell commands to run.

    Returns:
        Single-line shell command (without RUN keyword), or empty string if no hooks.
    """
    if not hooks:
        return ""

    # Chain commands with && for set -e equivalent behavior
    chained = " && ".join(hooks)
    return f"set -e && {chained}"


def generate_additional_packages_cmd(packages: list[str]) -> str:
    """Generate an inline command to install additional packages.

    This command detects the package manager and installs the specified packages.
    It assumes upgrade has already been run, so no update is performed.

    Args:
        packages: List of package names to install.

    Returns:
        Single-line shell command (without RUN keyword), or empty string if no packages.
    """
    if not packages:
        return ""

    pkg_list = " ".join(packages)
    return (
        f"set -e && "
        f"if command -v apk > /dev/null 2>&1; then apk add {pkg_list}; "
        f"elif command -v apt-get > /dev/null 2>&1; then apt-get install -y {pkg_list}; "
        f"elif command -v dnf > /dev/null 2>&1; then dnf install -y {pkg_list}; "
        f"elif command -v microdnf > /dev/null 2>&1; then microdnf install -y {pkg_list}; "
        f"elif command -v yum > /dev/null 2>&1; then yum install -y {pkg_list}; "
        f"elif command -v pacman > /dev/null 2>&1; then pacman -S --noconfirm {pkg_list}; "
        f"elif command -v zypper > /dev/null 2>&1; then zypper install -y {pkg_list}; "
        f'else echo "Unsupported distribution for additional packages" && exit 1; fi'
    )


def generate_upgrade_cmd() -> str:
    """Generate an inline command to upgrade all packages in the base image.

    Based on distrobox-init upgrade logic.

    Returns:
        Single-line shell command (without RUN keyword).
    """
    return (
        "set -e && "
        "if command -v apk > /dev/null 2>&1; then apk update && apk upgrade; "
        'elif command -v apt-get > /dev/null 2>&1; then apt-get update && apt-get upgrade -o Dpkg::Options::="--force-confold" -y; '
        "elif command -v dnf > /dev/null 2>&1; then dnf upgrade -y; "
        "elif command -v microdnf > /dev/null 2>&1; then microdnf upgrade -y; "
        "elif command -v yum > /dev/null 2>&1; then yum upgrade -y; "
        "elif command -v pacman > /dev/null 2>&1; then pacman -Syyu --noconfirm; "
        "elif command -v zypper > /dev/null 2>&1; then zypper dup -y; "
        'else echo "Unsupported distribution" && exit 1; fi'
    )


def generate_install_cmd(packages: dict[str, list[str]]) -> str:
    """Generate an inline command to install distrobox dependencies.

    The command detects the package manager available in the container
    and installs the appropriate packages. Based on distrobox-init logic.

    Note: This assumes upgrade has already been run, so no update needed.

    Args:
        packages: Dict mapping package manager names to package lists.
                  Keys: apk, apt, dnf, pacman, zypper

    Returns:
        Single-line shell command (without RUN keyword).
    """
    return (
        f"set -e && "
        f"if command -v apk > /dev/null 2>&1; then apk add {' '.join(packages['apk'])}; "
        f"elif command -v apt-get > /dev/null 2>&1; then apt-get install -y {' '.join(packages['apt'])}; "
        f"elif command -v dnf > /dev/null 2>&1; then dnf install -y {' '.join(packages['dnf'])}; "
        f"elif command -v microdnf > /dev/null 2>&1; then microdnf install -y {' '.join(packages['dnf'])}; "
        f"elif command -v yum > /dev/null 2>&1; then yum install -y {' '.join(packages['dnf'])}; "
        f"elif command -v pacman > /dev/null 2>&1; then pacman -S --noconfirm {' '.join(packages['pacman'])}; "
        f"elif command -v zypper > /dev/null 2>&1; then zypper install -y {' '.join(packages['zypper'])}; "
        f'else echo "Unsupported distribution" && exit 1; fi'
    )
