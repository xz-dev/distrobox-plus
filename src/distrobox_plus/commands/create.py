"""distrobox-create command implementation.

Creates a new distrobox container.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.request import urlopen
from urllib.error import URLError

import platformdirs

from ..config import (
    VERSION,
    Config,
    DEFAULT_IMAGE,
    DEFAULT_NAME,
    check_sudo_doas,
    get_user_info,
)
from ..container import detect_container_manager
from ..utils import (
    derive_container_name,
    get_hostname,
    validate_hostname,
    prompt_yes_no,
    get_script_path,
    mkdir_p,
    remove_trailing_slashes,
    find_ro_mountpoints,
    is_symlink,
    get_real_path,
    file_exists,
    print_ok,
    print_err,
)

if TYPE_CHECKING:
    from ..container import ContainerManager


def get_cache_dir() -> Path:
    """Get the distrobox cache directory."""
    return Path(platformdirs.user_cache_dir("distrobox"))


def show_compatibility() -> int:
    """Show list of compatible images, with local caching.

    Returns:
        Exit code (0 on success, 1 on failure)
    """
    cache_dir = get_cache_dir()
    cache_file = cache_dir / f"distrobox-compatibility-{VERSION}"

    # Try to use cached version
    if cache_file.exists() and cache_file.stat().st_size > 0:
        print(cache_file.read_text(), end="")
        return 0

    # Need to fetch from network
    url = f"https://raw.githubusercontent.com/89luca89/distrobox/{VERSION}/docs/compatibility.md"

    try:
        # Check connectivity first
        urlopen("https://github.com", timeout=5)
    except URLError:
        print(
            "ERROR: no cache file and no connectivity found, cannot retrieve compatibility list.",
            file=sys.stderr,
        )
        return 1

    try:
        with urlopen(url, timeout=30) as response:
            content = response.read().decode("utf-8")
    except URLError as e:
        print(f"ERROR: failed to fetch compatibility list: {e}", file=sys.stderr)
        return 1

    # Parse the markdown table to extract image list
    # Extract lines between | Alma... and | Void...
    images: list[str] = []
    in_table = False
    for line in content.splitlines():
        if line.startswith("| Alma"):
            in_table = True
        if in_table:
            # Extract 4th column (image names)
            parts = line.split("|")
            if len(parts) >= 4:
                image_cell = parts[3].strip()
                # Split by <br> and clean up
                for img in image_cell.replace("<br>", "\n").split("\n"):
                    img = img.strip()
                    if img:
                        images.append(img)
            if line.startswith("| Void"):
                break

    # Sort and deduplicate
    images = sorted(set(images))
    result = "\n".join(images) + "\n"

    # Cache the result
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(result)

    print(result, end="")
    return 0


@dataclass
class CreateOptions:
    """Options for container creation."""

    image: str = DEFAULT_IMAGE
    name: str = ""
    hostname: str = ""
    clone: str = ""
    custom_home: str = ""
    home_prefix: str = ""
    additional_volumes: list[str] = field(default_factory=list)
    additional_flags: list[str] = field(default_factory=list)
    additional_packages: str = ""
    init_hooks: str = ""
    pre_init_hooks: str = ""
    platform: str = ""
    pull: bool = False
    init: bool = False
    nvidia: bool = False
    nopasswd: bool = False
    no_entry: bool = False
    dryrun: bool = False

    # Unshare options
    unshare_ipc: bool = False
    unshare_groups: bool = False
    unshare_netns: bool = False
    unshare_process: bool = False
    unshare_devsys: bool = False


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-create."""
    # Get current hostname for default display
    current_hostname = get_hostname()

    epilog = f"""\
Examples:
    distrobox create --image alpine:latest --name test --init-hooks "touch /var/tmp/test1"
    distrobox create --image fedora:39 --name test --additional-flags "--env MY_VAR=value"
    distrobox create --clone fedora-39 --name fedora-39-copy
    distrobox create --image alpine my-alpine-container
    distrobox create --pull --image centos:stream9 --home ~/distrobox/centos9
    distrobox create --image alpine:latest --name test2 --additional-packages "git tmux vim"
    distrobox create --image ubuntu:22.04 --name ubuntu-nvidia --nvidia

    DBX_NON_INTERACTIVE=1 DBX_CONTAINER_NAME=test-alpine DBX_CONTAINER_IMAGE=alpine distrobox-create

Compatibility:
    For a list of compatible images and container managers, please consult the man page:
        man distrobox-compatibility
    or run:
        distrobox create --compatibility
    or consult: https://github.com/89luca89/distrobox/blob/main/docs/compatibility.md
"""

    parser = argparse.ArgumentParser(
        prog="distrobox-create",
        description="Create a new distrobox container",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "name_positional",
        nargs="?",
        help="Container name (positional)",
    )
    parser.add_argument(
        "-i",
        "--image",
        help=f"image to use for the container (default: {DEFAULT_IMAGE})",
    )
    parser.add_argument(
        "-n",
        "--name",
        help=f"name for the distrobox (default: {DEFAULT_NAME})",
    )
    parser.add_argument(
        "--hostname",
        help=f"hostname for the distrobox (default: {current_hostname})",
    )
    parser.add_argument(
        "-c",
        "--clone",
        help="name of the distrobox container to use as base for a new container. "
        "Useful to rename an existing distrobox or have multiple copies of the same environment",
    )
    parser.add_argument(
        "-H",
        "--home",
        help="select a custom HOME directory for the container. "
        "Useful to avoid host's home littering with temp files",
    )
    parser.add_argument(
        "--volume",
        action="append",
        default=[],
        help="additional volumes to add to the container",
    )
    parser.add_argument(
        "-a",
        "--additional-flags",
        action="append",
        default=[],
        help="additional flags to pass to the container manager command",
    )
    parser.add_argument(
        "-ap",
        "--additional-packages",
        action="append",
        default=[],
        help="additional packages to install during initial container setup",
    )
    parser.add_argument(
        "--init-hooks",
        help="additional commands to execute at the end of container initialization",
    )
    parser.add_argument(
        "--pre-init-hooks",
        help="additional commands to execute at the start of container initialization",
    )
    parser.add_argument(
        "--platform",
        help="specify which platform to use, eg: linux/arm64",
    )
    parser.add_argument(
        "-p",
        "--pull",
        action="store_true",
        help="pull the image even if it exists locally (implies --yes)",
    )
    parser.add_argument(
        "-I",
        "--init",
        action="store_true",
        help="use init system (like systemd) inside the container. "
        "This will make host's processes not visible from within the container (assumes --unshare-process). "
        "May require additional packages depending on the container image",
    )
    parser.add_argument(
        "--nvidia",
        action="store_true",
        help="try to integrate host's nVidia drivers in the guest",
    )
    parser.add_argument(
        "--no-entry",
        action="store_true",
        help="do not generate a container entry in the application list",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="only print the container manager command generated",
    )
    parser.add_argument(
        "-Y",
        "--yes",
        action="store_true",
        help="non-interactive, pull images without asking",
    )
    parser.add_argument(
        "-r",
        "--root",
        action="store_true",
        help="launch podman/docker/lilipod with root privileges. "
        "Do not use 'sudo distrobox'. Use DBX_SUDO_PROGRAM env var or "
        "distrobox_sudo_program config var to specify a different program (e.g. 'doas')",
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
    parser.add_argument(
        "-C",
        "--compatibility",
        action="store_true",
        help="show list of compatible images",
    )

    # Unshare options
    parser.add_argument(
        "--unshare-ipc",
        action="store_true",
        help="do not share ipc namespace with host",
    )
    parser.add_argument(
        "--unshare-groups",
        action="store_true",
        help="do not forward user's additional groups into the container",
    )
    parser.add_argument(
        "--unshare-netns",
        action="store_true",
        help="do not share the net namespace with host",
    )
    parser.add_argument(
        "--unshare-process",
        action="store_true",
        help="do not share process namespace with host",
    )
    parser.add_argument(
        "--unshare-devsys",
        action="store_true",
        help="do not share host devices and sysfs dirs from host",
    )
    parser.add_argument(
        "--unshare-all",
        action="store_true",
        help="activate all the unshare flags",
    )
    parser.add_argument(
        "--absolutely-disable-root-password-i-am-really-positively-sure",
        action="store_true",
        dest="nopasswd",
        help="[WARNING] when setting up a rootful distrobox, this will skip user password setup, leaving it blank",
    )

    return parser


def get_clone_image(manager: ContainerManager, clone_name: str) -> str | None:
    """Get image from cloning an existing container.

    Args:
        manager: Container manager
        clone_name: Name of container to clone

    Returns:
        Image tag for the cloned container, or None on failure
    """
    # Check container exists and is stopped
    status = manager.get_status(clone_name)
    if status is None:
        print(f"Container {clone_name} not found.", file=sys.stderr)
        return None

    if status == "running":
        print(f"Container {clone_name} is running.", file=sys.stderr)
        print(
            "Please stop it first. Cannot clone a running container.", file=sys.stderr
        )
        return None

    # Get container ID
    container_id = manager.inspect(clone_name, format_="{{.ID}}")
    if not container_id:
        print(f"Cannot get ID for container {clone_name}", file=sys.stderr)
        return None

    # Create commit tag
    commit_tag = f"{clone_name}:{date.today().isoformat()}".lower()

    print(f"Duplicating {clone_name}...", file=sys.stderr)
    if not manager.commit(str(container_id), commit_tag):
        print(f"Cannot clone container: {clone_name}", file=sys.stderr)
        return None

    return commit_tag


def _add_basic_settings(cmd: list[str], opts: CreateOptions) -> None:
    """Add basic container settings (platform, hostname, name, privileged)."""
    if opts.platform:
        cmd.append(f"--platform={opts.platform}")
    cmd.extend(
        [
            f"--hostname={opts.hostname}",
            f"--name={opts.name}",
            "--privileged",
            "--security-opt=label=disable",
            "--security-opt=apparmor=unconfined",
            "--pids-limit=-1",
            "--user=root:root",
        ]
    )


def _add_namespace_options(cmd: list[str], opts: CreateOptions) -> None:
    """Add namespace sharing options (ipc, network, pid)."""
    if not opts.unshare_ipc:
        cmd.append("--ipc=host")
    if not opts.unshare_netns:
        cmd.append("--network=host")
    if not opts.unshare_process:
        cmd.append("--pid=host")


def _add_environment_vars(
    cmd: list[str],
    opts: CreateOptions,
    manager_name: str,
    shell: str,
    container_home: str,
) -> None:
    """Add environment variables and labels."""
    cmd.extend(
        [
            "--label=manager=distrobox",
            f"--label=distrobox.unshare_groups={1 if opts.unshare_groups else 0}",
            f"--env=SHELL={Path(shell).name}",
            f"--env=HOME={container_home}",
            f"--env=container={manager_name}",
            "--env=TERMINFO_DIRS=/usr/share/terminfo:/run/host/usr/share/terminfo",
            f"--env=CONTAINER_ID={opts.name}",
        ]
    )


def _add_distrobox_volumes(cmd: list[str], home: str) -> tuple[Path | None, Path | None, Path | None]:
    """Add distrobox script volumes.

    Returns:
        Tuple of (entrypoint_path, export_path, hostexec_path)
    """
    entrypoint_path = get_script_path("distrobox-init")
    export_path = get_script_path("distrobox-export")
    hostexec_path = get_script_path("distrobox-host-exec")

    if not entrypoint_path or not export_path:
        print("Error: distrobox-init or distrobox-export not found", file=sys.stderr)
        sys.exit(127)

    cmd.append("--volume=/tmp:/tmp:rslave")
    cmd.append(f"--volume={entrypoint_path}:/usr/bin/entrypoint:ro")
    cmd.append(f"--volume={export_path}:/usr/bin/distrobox-export:ro")
    if hostexec_path:
        cmd.append(f"--volume={hostexec_path}:/usr/bin/distrobox-host-exec:ro")
    cmd.append(f"--volume={home}:{home}:rslave")

    return entrypoint_path, export_path, hostexec_path


def _add_rootfs_mounts(cmd: list[str], manager: ContainerManager) -> None:
    """Add root filesystem mounts (/:/run/host or per-directory for podman+runc)."""
    if manager.is_podman and manager.uses_runc():
        # Mount directories one by one for podman+runc compatibility
        ro_mounts = find_ro_mountpoints()
        for rootdir in Path("/").iterdir():
            if is_symlink(str(rootdir)):
                continue
            if str(rootdir) in ro_mounts:
                cmd.append(f"--volume={rootdir}:/run/host{rootdir}:ro,rslave")
            else:
                cmd.append(f"--volume={rootdir}:/run/host{rootdir}:rslave")
    else:
        cmd.append("--volume=/:/run/host/:rslave")


def _add_device_mounts(cmd: list[str], opts: CreateOptions) -> None:
    """Add /dev and /sys mounts."""
    if not opts.unshare_devsys:
        cmd.append("--volume=/dev:/dev:rslave")
        cmd.append("--volume=/sys:/sys:rslave")


def _add_init_mounts(cmd: list[str], opts: CreateOptions, manager: ContainerManager) -> None:
    """Add init system support mounts (tmpfs for /run, /run/lock, etc)."""
    if opts.init and manager.is_docker:
        cmd.append("--cgroupns=host")
    if opts.init and not manager.is_podman:
        cmd.extend(
            [
                "--stop-signal=SIGRTMIN+3",
                "--mount=type=tmpfs,destination=/run",
                "--mount=type=tmpfs,destination=/run/lock",
                "--mount=type=tmpfs,destination=/var/lib/journal",
            ]
        )


def _add_special_mounts(cmd: list[str], opts: CreateOptions) -> None:
    """Add special mounts: devpts, SELinux, journal, /dev/shm symlink."""
    # devpts handling
    if not opts.unshare_devsys:
        cmd.append("--volume=/dev/pts")
        cmd.append("--volume=/dev/null:/dev/ptmx")

    # SELinux workaround
    if file_exists("/sys/fs/selinux"):
        cmd.append("--volume=/sys/fs/selinux")

    # Journal ACL workaround
    cmd.append("--volume=/var/log/journal")

    # /dev/shm symlink handling
    if is_symlink("/dev/shm") and not opts.unshare_ipc:
        real_shm = get_real_path("/dev/shm")
        cmd.append(f"--volume={real_shm}:{real_shm}")


def _add_rhel_mounts(cmd: list[str]) -> None:
    """Add RHEL subscription file mounts."""
    rhel_files = [
        ("/etc/pki/entitlement/", "/run/secrets/etc-pki-entitlement", "ro"),
        ("/etc/rhsm/", "/run/secrets/rhsm", "ro"),
        ("/etc/yum.repos.d/redhat.repo", "/run/secrets/redhat.repo", "ro"),
    ]
    for src, dst, mode in rhel_files:
        if file_exists(src):
            cmd.append(f"--volume={src}:{dst}:{mode}")


def _add_home_mounts(
    cmd: list[str],
    opts: CreateOptions,
    user: str,
    home: str,
    uid: int,
) -> None:
    """Add custom home, /var/home, and XDG_RUNTIME_DIR mounts."""
    # Custom home handling
    if opts.custom_home:
        if not Path(opts.custom_home).exists():
            if not mkdir_p(opts.custom_home):
                print(f"Cannot create {opts.custom_home}", file=sys.stderr)
                sys.exit(1)
        cmd.append(f"--env=HOME={opts.custom_home}")
        cmd.append(f"--env=DISTROBOX_HOST_HOME={home}")
        cmd.append(f"--volume={opts.custom_home}:{opts.custom_home}:rslave")

    # Mount /var/home on ostree systems
    var_home = f"/var/home/{user}"
    if home != var_home and Path(var_home).is_dir():
        cmd.append(f"--volume={var_home}:{var_home}:rslave")

    # XDG_RUNTIME_DIR for non-init containers
    if not opts.init:
        runtime_dir = f"/run/user/{uid}"
        if Path(runtime_dir).is_dir():
            cmd.append(f"--volume={runtime_dir}:{runtime_dir}:rslave")


def _add_network_mounts(cmd: list[str], opts: CreateOptions) -> None:
    """Add network config file mounts (/etc/hosts, resolv.conf, hostname)."""
    if not opts.unshare_netns:
        for net_file in ["/etc/hosts", "/etc/resolv.conf"]:
            if file_exists(net_file):
                cmd.append(f"--volume={net_file}:{net_file}:ro")
        # Only mount /etc/hostname if not using custom hostname
        if opts.hostname == get_hostname() and file_exists("/etc/hostname"):
            cmd.append("--volume=/etc/hostname:/etc/hostname:ro")


def _add_podman_options(
    cmd: list[str],
    opts: CreateOptions,
    config: Config,
    manager: ContainerManager,
) -> None:
    """Add Podman-specific options (runtime, userns, systemd, etc)."""
    if not manager.is_podman:
        return

    if manager.has_crun():
        cmd.append("--runtime=crun")
    cmd.extend(
        [
            "--annotation=run.oci.keep_original_groups=1",
            "--ulimit=host",
        ]
    )
    if opts.init:
        cmd.append("--systemd=always")
    if not config.rootful:
        userns = "--userns=keep-id"
        # Check for keep-id:size support
        if not config.userns_nolimit and manager.supports_keepid_size(opts.image):
            userns += ":size=65536"
        cmd.append(userns)


def _add_additional_options(cmd: list[str], opts: CreateOptions) -> None:
    """Add additional volumes, flags, and nopasswd option."""
    # nopasswd flag
    if opts.nopasswd:
        cmd.append("--volume=/dev/null:/run/.nopasswd:ro")

    # Additional volumes
    for volume in opts.additional_volumes:
        cmd.append(f"--volume={volume}")

    # Additional flags
    for flag in opts.additional_flags:
        cmd.append(flag)


def _add_entrypoint_args(
    cmd: list[str],
    opts: CreateOptions,
    user: str,
    uid: int,
    gid: int,
    home: str,
) -> None:
    """Add entrypoint and its arguments."""
    cmd.append("--entrypoint=/usr/bin/entrypoint")
    cmd.append(opts.image)

    # Entrypoint arguments (use space-separated format for distrobox-init compatibility)
    cmd.extend(
        [
            "--verbose",
            "--name",
            user,
            "--user",
            str(uid),
            "--group",
            str(gid),
            "--home",
            opts.custom_home or home,
            "--init",
            str(1 if opts.init else 0),
            "--nvidia",
            str(1 if opts.nvidia else 0),
            "--pre-init-hooks",
            opts.pre_init_hooks,
            "--additional-packages",
            opts.additional_packages,
            "--",
            opts.init_hooks,
        ]
    )


def generate_create_command(
    manager: ContainerManager,
    opts: CreateOptions,
    config: Config,
) -> list[str]:
    """Generate the container create command.

    Args:
        manager: Container manager
        opts: Create options
        config: Configuration

    Returns:
        List of command arguments
    """
    user, home, shell = get_user_info()
    uid = os.getuid()
    gid = os.getgid()
    container_home = opts.custom_home or home

    cmd = ["create"]

    _add_basic_settings(cmd, opts)
    _add_namespace_options(cmd, opts)
    _add_environment_vars(cmd, opts, manager.name, shell, container_home)
    _add_distrobox_volumes(cmd, home)
    _add_rootfs_mounts(cmd, manager)
    _add_device_mounts(cmd, opts)
    _add_init_mounts(cmd, opts, manager)
    _add_special_mounts(cmd, opts)
    _add_rhel_mounts(cmd)
    _add_home_mounts(cmd, opts, user, home, uid)
    _add_network_mounts(cmd, opts)
    _add_podman_options(cmd, opts, config, manager)
    _add_additional_options(cmd, opts)
    _add_entrypoint_args(cmd, opts, user, uid, gid, home)

    return cmd


def _print_sudo_error() -> int:
    """Print error message when running via sudo/doas."""
    print(
        f"Running {sys.argv[0]} via SUDO/DOAS is not supported.",
        file=sys.stderr,
    )
    print(
        f"Instead, please try running:\n  {sys.argv[0]} --root",
        file=sys.stderr,
    )
    return 1


def _apply_cli_overrides(config: Config, parsed: argparse.Namespace) -> None:
    """Apply command line overrides to config."""
    if parsed.root:
        config.rootful = True
    if parsed.verbose:
        config.verbose = True
    if parsed.yes or parsed.pull:
        config.non_interactive = True


def _resolve_image(parsed: argparse.Namespace, config: Config, clone: str) -> str:
    """Resolve the container image from parsed args and config."""
    if parsed.image:
        return parsed.image
    if config.container_image:
        return config.container_image
    if not clone:
        return DEFAULT_IMAGE
    return ""


def _resolve_name(parsed: argparse.Namespace, config: Config, image: str) -> str:
    """Resolve the container name from parsed args and config."""
    if parsed.name:
        return parsed.name
    if parsed.name_positional:
        return parsed.name_positional
    if config.container_name:
        return config.container_name
    if image == DEFAULT_IMAGE:
        return DEFAULT_NAME
    if image:
        return derive_container_name(image)
    return ""


def _resolve_hostname(
    parsed: argparse.Namespace,
    config: Config,
    name: str,
) -> str | None:
    """Resolve and validate hostname. Returns None on validation failure."""
    hostname = parsed.hostname or config.container_hostname or get_hostname()
    if parsed.unshare_netns:
        hostname = f"{name}.{hostname}"

    if not validate_hostname(hostname):
        print(
            f"Error: Invalid hostname '{hostname}', longer than 64 characters",
            file=sys.stderr,
        )
        print("Use --hostname argument to set it manually", file=sys.stderr)
        return None

    return hostname


def _resolve_custom_home(
    parsed: argparse.Namespace,
    config: Config,
    name: str,
) -> str:
    """Resolve custom home directory from parsed args and config."""
    if parsed.home:
        return remove_trailing_slashes(parsed.home)
    if config.container_custom_home:
        return config.container_custom_home
    if config.container_home_prefix:
        return f"{config.container_home_prefix}/{name}"
    return ""


def _set_unshare_options(opts: CreateOptions, parsed: argparse.Namespace) -> None:
    """Set unshare options based on parsed arguments."""
    if parsed.unshare_all:
        opts.unshare_ipc = True
        opts.unshare_groups = True
        opts.unshare_netns = True
        opts.unshare_process = True
        opts.unshare_devsys = True
    else:
        opts.unshare_ipc = parsed.unshare_ipc
        opts.unshare_groups = parsed.unshare_groups or parsed.init
        opts.unshare_netns = parsed.unshare_netns
        opts.unshare_process = parsed.unshare_process or parsed.init
        opts.unshare_devsys = parsed.unshare_devsys


def _build_create_options(
    parsed: argparse.Namespace,
    config: Config,
) -> CreateOptions | None:
    """Build CreateOptions from parsed arguments and config.

    Returns:
        CreateOptions if successful, None if validation failed
    """
    opts = CreateOptions()
    opts.clone = parsed.clone or ""
    opts.image = _resolve_image(parsed, config, opts.clone)
    opts.name = _resolve_name(parsed, config, opts.image)

    hostname = _resolve_hostname(parsed, config, opts.name)
    if hostname is None:
        return None
    opts.hostname = hostname

    opts.custom_home = _resolve_custom_home(parsed, config, opts.name)

    # Direct assignments
    opts.additional_volumes = parsed.volume
    opts.additional_flags = parsed.additional_flags
    opts.additional_packages = " ".join(parsed.additional_packages)
    opts.init_hooks = parsed.init_hooks or ""
    opts.pre_init_hooks = parsed.pre_init_hooks or ""
    opts.platform = parsed.platform or ""
    opts.pull = parsed.pull or config.container_always_pull
    opts.init = parsed.init
    opts.nvidia = parsed.nvidia
    opts.nopasswd = parsed.nopasswd
    opts.no_entry = parsed.no_entry or not config.container_generate_entry
    opts.dryrun = parsed.dry_run

    _set_unshare_options(opts, parsed)

    return opts


def _handle_clone(
    manager: ContainerManager,
    opts: CreateOptions,
) -> str | None:
    """Handle clone logic.

    Returns:
        Clone image name if successful, None if failed
    """
    if not manager.is_podman and not manager.is_docker:
        print(
            "Error: clone is only supported with docker and podman", file=sys.stderr
        )
        return None
    return get_clone_image(manager, opts.clone)


def _print_enter_hint(name: str, rootful: bool) -> None:
    """Print hint message for entering the container."""
    print("To enter, run:\n")
    if rootful and os.getuid() != 0:
        print(f"distrobox enter --root {name}\n")
    else:
        print(f"distrobox enter {name}\n")


def _ensure_image(
    manager: ContainerManager,
    opts: CreateOptions,
    config: Config,
) -> bool:
    """Ensure image exists, pulling if necessary.

    Returns:
        True on success, False on failure
    """
    if not opts.pull and manager.image_exists(opts.image):
        return True

    if not config.non_interactive and not opts.pull:
        print(f"Image {opts.image} not found.", file=sys.stderr)
        if not prompt_yes_no("Do you want to pull the image now?"):
            print(
                f"Next time, run: {manager.name} pull {opts.image}", file=sys.stderr
            )
            return False

    if not manager.pull(opts.image, opts.platform or None):
        print(f"Failed to pull {opts.image}", file=sys.stderr)
        return False

    return True


def _execute_create(
    manager: ContainerManager,
    opts: CreateOptions,
    config: Config,
) -> int:
    """Execute container creation and handle result.

    Returns:
        Exit code
    """
    print(f"Creating '{opts.name}' using image {opts.image}\t", end="", file=sys.stderr)

    cmd = generate_create_command(manager, opts, config)
    result = manager.run(*cmd, capture_output=True)

    if result.returncode == 0:
        print_ok()
        print(f"Distrobox '{opts.name}' successfully created.", file=sys.stderr)
        _print_enter_hint(opts.name, config.rootful)

        # Generate desktop entry
        if not config.rootful and not opts.no_entry:
            genentry = get_script_path("distrobox-generate-entry")
            if genentry:
                subprocess.run([str(genentry), opts.name], capture_output=True)

        return 0
    else:
        print_err()
        print("Failed to create container.", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-create command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    if check_sudo_doas():
        return _print_sudo_error()

    parser = create_parser()
    parsed = parser.parse_args(args)

    if parsed.compatibility:
        return show_compatibility()

    config = Config.load()
    _apply_cli_overrides(config, parsed)

    opts = _build_create_options(parsed, config)
    if opts is None:
        return 1

    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    # Handle clone
    if opts.clone:
        clone_image = _handle_clone(manager, opts)
        if not clone_image:
            return 1 if manager.is_podman or manager.is_docker else 127
        opts.image = clone_image

    # Dry run
    if opts.dryrun:
        cmd = generate_create_command(manager, opts, config)
        full_cmd = manager.cmd_prefix + cmd
        print(" ".join(full_cmd))
        return 0

    # Check if container already exists
    if manager.exists(opts.name):
        print(f"Distrobox named '{opts.name}' already exists.")
        _print_enter_hint(opts.name, config.rootful)
        return 0

    # Check/pull image
    if not _ensure_image(manager, opts, config):
        # User declined to pull - return 0 (not an error)
        if not opts.pull and not config.non_interactive:
            return 0
        return 1

    return _execute_create(manager, opts, config)


if __name__ == "__main__":
    sys.exit(run())
