"""Template generation utilities for Containerfile creation.

Generates package installation commands using Jinja2 templating.
"""

from __future__ import annotations

from jinja2 import BaseLoader, Environment

# Jinja2 environment (singleton)
_env = Environment(loader=BaseLoader(), trim_blocks=True, lstrip_blocks=True)

# Package manager configuration
_PM_CONFIG: dict[str, dict[str, str]] = {
    "apk": {
        "detect": "apk",
        "check": "apk info -e {pkg} > /dev/null 2>&1",
        "install": "apk add --no-cache",
        "update": "apk update",
        "upgrade": "apk update && apk upgrade",
    },
    "apt": {
        "detect": "apt-get",
        "exclude": "rpm",
        "check": "dpkg -s {pkg} > /dev/null 2>&1",
        "install": "apt-get install -y",
        "update": "export DEBIAN_FRONTEND=noninteractive && apt-get update",
        "upgrade": "export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get upgrade -y",
    },
    "dnf": {
        "detect": "dnf",
        "fallback": "yum",
        "check": "rpm -q {pkg} > /dev/null 2>&1",
        "install": "dnf install -y",
        "install_fallback": "yum install -y",
        "upgrade": "dnf upgrade -y",
    },
    "pacman": {
        "detect": "pacman",
        "check": "pacman -Qi {pkg} > /dev/null 2>&1",
        "install": "pacman -S --noconfirm --needed",
        "update": "pacman -Sy",
        "upgrade": "pacman -Syu --noconfirm",
    },
    "zypper": {
        "detect": "zypper",
        "check": "rpm -q {pkg} > /dev/null 2>&1",
        "install": "zypper install -y",
        "update": "zypper refresh",
        "upgrade": "zypper dup -y",
    },
    "emerge": {
        "detect": "emerge",
        "check": "command -v {pkg_name} > /dev/null 2>&1",
        "install": "emerge --ask=n --noreplace --quiet-build",
        "install_user": "emerge --ask=n --noreplace",  # For user packages (no --quiet-build)
        "upgrade": "emerge --sync",
    },
    "xbps": {
        "detect": "xbps-install",
        "check": "xbps-query {pkg} > /dev/null 2>&1",
        "install": "xbps-install -y",
        "update": "xbps-install -Syu xbps",
        "upgrade": "xbps-install -Syu",
    },
}

# Core packages needed by distrobox for each package manager
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

# Pre-compiled Jinja2 templates
_INSTALL_TEMPLATE = _env.from_string("""\
set -e
{%- for pm, cfg in configs.items() %}
 && if command -v {{ cfg.detect }} > /dev/null 2>&1{% if cfg.exclude %} && ! command -v {{ cfg.exclude }} > /dev/null 2>&1{% endif %}{% if cfg.fallback %} || command -v {{ cfg.fallback }} > /dev/null 2>&1{% endif %}; then \
{% if cfg.update %}{{ cfg.update }} && {% endif %}\
{%- for pkg in packages[pm][:limits.get(pm, 10)] %}
{{ cfg.check.format(pkg=pkg, pkg_name=pkg.split('/')[-1]) }} || {{ cfg.install }} {{ pkg }}{% if cfg.install_fallback %} || {{ cfg.install_fallback }} {{ pkg }}{% endif %} || true{% if not loop.last %} && {% endif %}\
{%- endfor %}; fi\
{%- endfor %}""")

_INSTALL_FULL_TEMPLATE = _env.from_string("""\
set -e\
{%- for pm, cfg in configs.items() %} && \
if command -v {{ cfg.detect }} > /dev/null 2>&1{% if cfg.exclude %} && ! command -v {{ cfg.exclude }} > /dev/null 2>&1{% endif %}; then \
{% if cfg.update %}{{ cfg.update }} && {% endif %}{{ cfg.install }} {{ packages[pm] | join(' ') }} || true; \
{%- if cfg.fallback %}elif command -v {{ cfg.fallback }} > /dev/null 2>&1; then {{ cfg.install_fallback }} {{ packages[pm] | join(' ') }} || true; {% endif %}\
fi\
{%- endfor %}""")

_UPGRADE_TEMPLATE = _env.from_string("""\
set -e && \
{%- for pm, cfg in configs.items() %}\
{% if not loop.first %}elif {% else %}if {% endif %}\
command -v {{ cfg.detect }} > /dev/null 2>&1; then {{ cfg.upgrade }} || true\
{%- endfor %}; fi""")

_ADDITIONAL_PKG_TEMPLATE = _env.from_string("""\
set -e && \
{%- for pm, cfg in configs.items() %}\
{% if not loop.first %}elif {% else %}if {% endif %}\
command -v {{ cfg.detect }} > /dev/null 2>&1{% if cfg.exclude %} && ! command -v {{ cfg.exclude }} > /dev/null 2>&1{% endif %}; then \
{% if 'update' in cfg and pm == 'apt' %}{{ cfg.update }} && {% endif %}{{ cfg.install_user if cfg.install_user else cfg.install }} {{ pkg_list }}\
{%- endfor %}; fi""")


def _escape_shell(s: str) -> str:
    """Escape string for shell use in Containerfile."""
    return s.replace("'", "'\"'\"'")


def generate_install_cmd() -> str:
    """Generate install command with conditional package checks (limited packages)."""
    return _INSTALL_TEMPLATE.render(
        configs=_PM_CONFIG, packages=DISTROBOX_PACKAGES, limits={"emerge": 8}
    )


def generate_install_cmd_full() -> str:
    """Generate comprehensive install command for all package managers."""
    return _INSTALL_FULL_TEMPLATE.render(
        configs=_PM_CONFIG, packages=DISTROBOX_PACKAGES
    )


def generate_upgrade_cmd() -> str:
    """Generate package manager upgrade command."""
    return _UPGRADE_TEMPLATE.render(configs=_PM_CONFIG)


def generate_hooks_cmd(hooks: str) -> str:
    """Generate command to run hooks."""
    return f"set -e && {_escape_shell(hooks)}" if hooks else "true"


def generate_additional_packages_cmd(packages: str) -> str:
    """Generate conditional install command for user-specified packages."""
    return (
        _ADDITIONAL_PKG_TEMPLATE.render(configs=_PM_CONFIG, pkg_list=packages.strip())
        if packages
        else "true"
    )
