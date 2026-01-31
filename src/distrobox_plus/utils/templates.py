"""Template generation utilities for Containerfile creation.

Generates package installation commands with conditional checks to
optimize builds for source-based distros like Gentoo.
"""

from __future__ import annotations

# Core packages needed by distrobox for each package manager
# These are the minimal essential packages that distrobox-init installs
DISTROBOX_PACKAGES: dict[str, list[str]] = {
    "apk": [
        "bash",
        "bc",
        "bzip2",
        "coreutils",
        "curl",
        "diffutils",
        "findmnt",
        "findutils",
        "gnupg",
        "gpg",
        "iproute2",
        "iputils",
        "keyutils",
        "less",
        "libcap",
        "mount",
        "ncurses",
        "ncurses-terminfo",
        "net-tools",
        "pigz",
        "rsync",
        "shadow",
        "sudo",
        "tcpdump",
        "tree",
        "tzdata",
        "umount",
        "unzip",
        "util-linux",
        "util-linux-login",
        "util-linux-misc",
        "vulkan-loader",
        "wget",
        "xauth",
        "xz",
        "zip",
    ],
    "apt": [
        "apt-utils",
        "bash",
        "bash-completion",
        "bc",
        "bzip2",
        "curl",
        "dialog",
        "diffutils",
        "findutils",
        "gnupg",
        "gnupg2",
        "gpgsm",
        "hostname",
        "iproute2",
        "iputils-ping",
        "keyutils",
        "less",
        "libcap2-bin",
        "libkrb5-3",
        "libnss-mdns",
        "libnss-myhostname",
        "locales",
        "lsof",
        "man-db",
        "manpages",
        "mtr",
        "ncurses-base",
        "openssh-client",
        "passwd",
        "pigz",
        "pinentry-curses",
        "procps",
        "rsync",
        "sudo",
        "tcpdump",
        "time",
        "traceroute",
        "tree",
        "tzdata",
        "unzip",
        "util-linux",
        "wget",
        "xauth",
        "xz-utils",
        "zip",
    ],
    "dnf": [
        "bash",
        "bash-completion",
        "bc",
        "bzip2",
        "cracklib-dicts",
        "curl",
        "diffutils",
        "dnf-plugins-core",
        "findutils",
        "glibc-all-langpacks",
        "glibc-common",
        "glibc-locale-source",
        "gnupg2",
        "gnupg2-smime",
        "hostname",
        "iproute",
        "iputils",
        "keyutils",
        "krb5-libs",
        "less",
        "lsof",
        "man-db",
        "man-pages",
        "mtr",
        "ncurses",
        "nss-mdns",
        "openssh-clients",
        "pam",
        "passwd",
        "pigz",
        "pinentry",
        "procps-ng",
        "rsync",
        "shadow-utils",
        "sudo",
        "tcpdump",
        "time",
        "traceroute",
        "tree",
        "tzdata",
        "unzip",
        "util-linux",
        "util-linux-script",
        "vte-profile",
        "wget",
        "which",
        "whois",
        "words",
        "xorg-x11-xauth",
        "xz",
        "zip",
        "mesa-dri-drivers",
        "mesa-vulkan-drivers",
    ],
    "pacman": [
        "bash",
        "bash-completion",
        "bc",
        "curl",
        "diffutils",
        "findutils",
        "glibc",
        "gnupg",
        "iputils",
        "inetutils",
        "keyutils",
        "less",
        "lsof",
        "man-db",
        "man-pages",
        "mlocate",
        "mtr",
        "ncurses",
        "nss-mdns",
        "openssh",
        "pigz",
        "pinentry",
        "procps-ng",
        "rsync",
        "shadow",
        "sudo",
        "tcpdump",
        "time",
        "traceroute",
        "tree",
        "tzdata",
        "unzip",
        "util-linux",
        "util-linux-libs",
        "vte-common",
        "wget",
        "words",
        "xorg-xauth",
        "zip",
        "mesa",
    ],
    "zypper": [
        "bash",
        "bash-completion",
        "bc",
        "bzip2",
        "curl",
        "diffutils",
        "findutils",
        "glibc-locale",
        "glibc-locale-base",
        "gnupg",
        "hostname",
        "iputils",
        "keyutils",
        "less",
        "lsof",
        "man",
        "man-pages",
        "mtr",
        "ncurses",
        "nss-mdns",
        "openssh-clients",
        "pam",
        "pam-extra",
        "pigz",
        "pinentry",
        "procps",
        "rsync",
        "shadow",
        "sudo",
        "system-group-wheel",
        "systemd",
        "time",
        "timezone",
        "tree",
        "unzip",
        "util-linux",
        "util-linux-systemd",
        "wget",
        "words",
        "xauth",
        "zip",
        "Mesa-dri",
        "libvulkan1",
    ],
    "emerge": [
        "app-crypt/gnupg",
        "app-crypt/pinentry",
        "app-shells/bash",
        "app-shells/bash-completion",
        "net-misc/curl",
        "net-misc/wget",
        "sys-apps/diffutils",
        "sys-apps/findutils",
        "sys-apps/less",
        "sys-apps/shadow",
        "sys-apps/util-linux",
        "sys-devel/bc",
        "sys-libs/ncurses",
        "sys-process/lsof",
        "sys-process/procps",
        "app-admin/sudo",
    ],
    "xbps": [
        "bash",
        "bash-completion",
        "bc",
        "bzip2",
        "curl",
        "diffutils",
        "findutils",
        "gnupg2",
        "inetutils-ping",
        "iproute2",
        "less",
        "lsof",
        "man-db",
        "mit-krb5-client",
        "mit-krb5-libs",
        "mtr",
        "ncurses-base",
        "nss",
        "openssh",
        "pigz",
        "pinentry-tty",
        "procps-ng",
        "rsync",
        "shadow",
        "sudo",
        "time",
        "traceroute",
        "tree",
        "tzdata",
        "unzip",
        "util-linux",
        "xauth",
        "xz",
        "zip",
        "wget",
        "vte3",
        "mesa-dri",
        "vulkan-loader",
    ],
}


def _escape_shell(s: str) -> str:
    """Escape string for shell use in Containerfile.

    Args:
        s: String to escape

    Returns:
        Shell-safe string
    """
    # For RUN commands, we escape single quotes
    return s.replace("'", "'\"'\"'")


def generate_install_cmd() -> str:
    """Generate install command with conditional package checks.

    Uses `command -v pkg || install pkg` pattern to skip packages
    that are already installed. This is critical for source-based
    distros like Gentoo to avoid recompilation.

    Returns:
        Shell command string for Containerfile RUN
    """
    lines = ["set -e"]

    # APK (Alpine, Wolfi, Chimera)
    apk_packages = DISTROBOX_PACKAGES["apk"]
    apk_checks = []
    for pkg in apk_packages:
        # For apk, we check if the package is installed, not just the command
        apk_checks.append(
            f"apk info -e {pkg} > /dev/null 2>&1 || apk add --no-cache {pkg} || true"
        )

    lines.append(
        f"if command -v apk > /dev/null 2>&1; then "
        f"apk update && "
        f"{' && '.join(apk_checks[:10])}; "  # Limit for readability in generated file
        f"fi"
    )

    # APT (Debian, Ubuntu)
    apt_packages = DISTROBOX_PACKAGES["apt"]
    apt_checks = []
    for pkg in apt_packages:
        apt_checks.append(
            f"dpkg -s {pkg} > /dev/null 2>&1 || apt-get install -y {pkg} || true"
        )

    lines.append(
        f"if command -v apt-get > /dev/null 2>&1 && ! command -v rpm > /dev/null 2>&1; then "
        f"export DEBIAN_FRONTEND=noninteractive && "
        f"apt-get update && "
        f"{' && '.join(apt_checks[:10])}; "
        f"fi"
    )

    # DNF/YUM (Fedora, RHEL, CentOS)
    dnf_packages = DISTROBOX_PACKAGES["dnf"]
    dnf_checks = []
    for pkg in dnf_packages:
        dnf_checks.append(
            f"rpm -q {pkg} > /dev/null 2>&1 || dnf install -y {pkg} || yum install -y {pkg} || true"
        )

    lines.append(
        f"if command -v dnf > /dev/null 2>&1 || command -v yum > /dev/null 2>&1; then "
        f"{' && '.join(dnf_checks[:10])}; "
        f"fi"
    )

    # Pacman (Arch Linux)
    pacman_packages = DISTROBOX_PACKAGES["pacman"]
    pacman_checks = []
    for pkg in pacman_packages:
        pacman_checks.append(
            f"pacman -Qi {pkg} > /dev/null 2>&1 || pacman -S --noconfirm --needed {pkg} || true"
        )

    lines.append(
        f"if command -v pacman > /dev/null 2>&1; then "
        f"pacman -Sy && "
        f"{' && '.join(pacman_checks[:10])}; "
        f"fi"
    )

    # Zypper (openSUSE)
    zypper_packages = DISTROBOX_PACKAGES["zypper"]
    zypper_checks = []
    for pkg in zypper_packages:
        zypper_checks.append(
            f"rpm -q {pkg} > /dev/null 2>&1 || zypper install -y {pkg} || true"
        )

    lines.append(
        f"if command -v zypper > /dev/null 2>&1; then "
        f"zypper refresh && "
        f"{' && '.join(zypper_checks[:10])}; "
        f"fi"
    )

    # Emerge (Gentoo) - Most important for conditional checks due to compile time
    emerge_packages = DISTROBOX_PACKAGES["emerge"]
    emerge_checks = []
    for pkg in emerge_packages:
        # For emerge, --noreplace already skips installed packages
        # but we add explicit check for clarity and to avoid even invoking emerge
        pkg_name = pkg.split("/")[-1] if "/" in pkg else pkg
        emerge_checks.append(
            f"command -v {pkg_name} > /dev/null 2>&1 || "
            f"emerge --ask=n --noreplace --quiet-build {pkg} || true"
        )

    lines.append(
        f"if command -v emerge > /dev/null 2>&1; then "
        f"{' && '.join(emerge_checks[:8])}; "
        f"fi"
    )

    # XBPS (Void Linux)
    xbps_packages = DISTROBOX_PACKAGES["xbps"]
    xbps_checks = []
    for pkg in xbps_packages:
        xbps_checks.append(
            f"xbps-query {pkg} > /dev/null 2>&1 || xbps-install -y {pkg} || true"
        )

    lines.append(
        f"if command -v xbps-install > /dev/null 2>&1; then "
        f"xbps-install -Syu xbps && "
        f"{' && '.join(xbps_checks[:10])}; "
        f"fi"
    )

    return " && ".join(lines)


def generate_install_cmd_full() -> str:
    """Generate comprehensive install command for all package managers.

    This version includes all packages (not limited for readability).
    Used internally for complete builds.

    Returns:
        Shell command string for Containerfile RUN
    """
    sections = []

    # APK
    apk_pkgs = " ".join(DISTROBOX_PACKAGES["apk"])
    sections.append(
        f"if command -v apk > /dev/null 2>&1; then "
        f"apk update && apk add --no-cache {apk_pkgs} || true; "
        f"fi"
    )

    # APT (excluding rpm-based apt systems)
    apt_pkgs = " ".join(DISTROBOX_PACKAGES["apt"])
    sections.append(
        f"if command -v apt-get > /dev/null 2>&1 && ! command -v rpm > /dev/null 2>&1; then "
        f"export DEBIAN_FRONTEND=noninteractive && "
        f"apt-get update && apt-get install -y {apt_pkgs} || true; "
        f"fi"
    )

    # DNF/YUM
    dnf_pkgs = " ".join(DISTROBOX_PACKAGES["dnf"])
    sections.append(
        f"if command -v dnf > /dev/null 2>&1; then "
        f"dnf install -y {dnf_pkgs} || true; "
        f"elif command -v yum > /dev/null 2>&1; then "
        f"yum install -y {dnf_pkgs} || true; "
        f"fi"
    )

    # Pacman
    pacman_pkgs = " ".join(DISTROBOX_PACKAGES["pacman"])
    sections.append(
        f"if command -v pacman > /dev/null 2>&1; then "
        f"pacman -Syu --noconfirm && pacman -S --noconfirm --needed {pacman_pkgs} || true; "
        f"fi"
    )

    # Zypper
    zypper_pkgs = " ".join(DISTROBOX_PACKAGES["zypper"])
    sections.append(
        f"if command -v zypper > /dev/null 2>&1; then "
        f"zypper refresh && zypper install -y {zypper_pkgs} || true; "
        f"fi"
    )

    # Emerge
    emerge_pkgs = " ".join(DISTROBOX_PACKAGES["emerge"])
    sections.append(
        f"if command -v emerge > /dev/null 2>&1; then "
        f"emerge --ask=n --noreplace --quiet-build {emerge_pkgs} || true; "
        f"fi"
    )

    # XBPS
    xbps_pkgs = " ".join(DISTROBOX_PACKAGES["xbps"])
    sections.append(
        f"if command -v xbps-install > /dev/null 2>&1; then "
        f"xbps-install -Syu xbps && xbps-install -y {xbps_pkgs} || true; "
        f"fi"
    )

    return "set -e && " + " && ".join(sections)


def generate_upgrade_cmd() -> str:
    """Generate package manager upgrade command.

    Returns:
        Shell command string that upgrades packages based on detected manager
    """
    return (
        "set -e && "
        "if command -v apk > /dev/null 2>&1; then apk update && apk upgrade || true; "
        "elif command -v apt-get > /dev/null 2>&1; then "
        "export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get upgrade -y || true; "
        "elif command -v dnf > /dev/null 2>&1; then dnf upgrade -y || true; "
        "elif command -v yum > /dev/null 2>&1; then yum upgrade -y || true; "
        "elif command -v pacman > /dev/null 2>&1; then pacman -Syu --noconfirm || true; "
        "elif command -v zypper > /dev/null 2>&1; then zypper dup -y || true; "
        "elif command -v emerge > /dev/null 2>&1; then emerge --sync || true; "
        "elif command -v xbps-install > /dev/null 2>&1; then xbps-install -Syu || true; "
        "fi"
    )


def generate_hooks_cmd(hooks: str) -> str:
    """Generate command to run hooks.

    Chains hooks with && for set -e behavior.

    Args:
        hooks: Hook commands (may contain multiple commands)

    Returns:
        Shell command string
    """
    if not hooks:
        return "true"

    # Escape for shell and chain with &&
    escaped = _escape_shell(hooks)
    return f"set -e && {escaped}"


def generate_additional_packages_cmd(packages: str) -> str:
    """Generate conditional install command for user-specified packages.

    Args:
        packages: Space-separated list of packages

    Returns:
        Shell command string
    """
    if not packages:
        return "true"

    pkg_list = packages.strip()

    return (
        "set -e && "
        f"if command -v apk > /dev/null 2>&1; then apk add --no-cache {pkg_list}; "
        f"elif command -v apt-get > /dev/null 2>&1 && ! command -v rpm > /dev/null 2>&1; then "
        f"export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y {pkg_list}; "
        f"elif command -v dnf > /dev/null 2>&1; then dnf install -y {pkg_list}; "
        f"elif command -v yum > /dev/null 2>&1; then yum install -y {pkg_list}; "
        f"elif command -v pacman > /dev/null 2>&1; then pacman -S --noconfirm --needed {pkg_list}; "
        f"elif command -v zypper > /dev/null 2>&1; then zypper install -y {pkg_list}; "
        f"elif command -v emerge > /dev/null 2>&1; then emerge --ask=n --noreplace {pkg_list}; "
        f"elif command -v xbps-install > /dev/null 2>&1; then xbps-install -y {pkg_list}; "
        "fi"
    )
