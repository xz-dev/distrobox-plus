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

from ..config import VERSION, Config, DEFAULT_IMAGE, DEFAULT_NAME, check_sudo_doas, get_user_info
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
        print("ERROR: no cache file and no connectivity found, cannot retrieve compatibility list.",
              file=sys.stderr)
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
    parser = argparse.ArgumentParser(
        prog="distrobox-create",
        description="Create a new distrobox container",
    )
    parser.add_argument(
        "name_positional",
        nargs="?",
        help="Container name (positional)",
    )
    parser.add_argument(
        "-i", "--image",
        help=f"Image to use (default: {DEFAULT_IMAGE})",
    )
    parser.add_argument(
        "-n", "--name",
        help=f"Name for the distrobox (default: {DEFAULT_NAME})",
    )
    parser.add_argument(
        "--hostname",
        help="Hostname for the distrobox",
    )
    parser.add_argument(
        "-c", "--clone",
        help="Clone an existing distrobox",
    )
    parser.add_argument(
        "-H", "--home",
        help="Custom HOME directory",
    )
    parser.add_argument(
        "--volume",
        action="append",
        default=[],
        help="Additional volumes to mount",
    )
    parser.add_argument(
        "-a", "--additional-flags",
        action="append",
        default=[],
        help="Additional flags for container manager",
    )
    parser.add_argument(
        "-ap", "--additional-packages",
        action="append",
        default=[],
        help="Additional packages to install (can be specified multiple times)",
    )
    parser.add_argument(
        "--init-hooks",
        help="Commands to run at end of initialization",
    )
    parser.add_argument(
        "--pre-init-hooks",
        help="Commands to run at start of initialization",
    )
    parser.add_argument(
        "--platform",
        help="Platform specification (e.g., linux/arm64)",
    )
    parser.add_argument(
        "-p", "--pull",
        action="store_true",
        help="Pull image even if it exists locally",
    )
    parser.add_argument(
        "-I", "--init",
        action="store_true",
        help="Use init system inside container",
    )
    parser.add_argument(
        "--nvidia",
        action="store_true",
        help="Integrate host nVidia drivers",
    )
    parser.add_argument(
        "--no-entry",
        action="store_true",
        help="Don't generate application entry",
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Print command without executing",
    )
    parser.add_argument(
        "-Y", "--yes",
        action="store_true",
        help="Non-interactive mode",
    )
    parser.add_argument(
        "-r", "--root",
        action="store_true",
        help="Launch with root privileges",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show more verbosity",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"distrobox: {VERSION}",
    )
    parser.add_argument(
        "-C", "--compatibility",
        action="store_true",
        help="Show list of compatible images",
    )

    # Unshare options
    parser.add_argument(
        "--unshare-ipc",
        action="store_true",
        help="Do not share ipc namespace with host",
    )
    parser.add_argument(
        "--unshare-groups",
        action="store_true",
        help="Do not forward user's additional groups into the container",
    )
    parser.add_argument(
        "--unshare-netns",
        action="store_true",
        help="Do not share the net namespace with host",
    )
    parser.add_argument(
        "--unshare-process",
        action="store_true",
        help="Do not share process namespace with host",
    )
    parser.add_argument(
        "--unshare-devsys",
        action="store_true",
        help="Do not share host devices and sysfs dirs from host",
    )
    parser.add_argument(
        "--unshare-all",
        action="store_true",
        help="Activate all the unshare flags",
    )
    parser.add_argument(
        "--absolutely-disable-root-password-i-am-really-positively-sure",
        action="store_true",
        dest="nopasswd",
        help="Skip root password setup for rootful containers",
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
        print("Please stop it first. Cannot clone a running container.", file=sys.stderr)
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

    # Get script paths
    entrypoint_path = get_script_path("distrobox-init")
    export_path = get_script_path("distrobox-export")
    hostexec_path = get_script_path("distrobox-host-exec")

    if not entrypoint_path or not export_path:
        print("Error: distrobox-init or distrobox-export not found", file=sys.stderr)
        sys.exit(127)

    # Determine container home
    container_home = opts.custom_home or home

    cmd = ["create"]

    # Platform
    if opts.platform:
        cmd.append(f"--platform={opts.platform}")

    # Basic container settings
    cmd.extend([
        f"--hostname={opts.hostname}",
        f"--name={opts.name}",
        "--privileged",
        "--security-opt=label=disable",
        "--security-opt=apparmor=unconfined",
        "--pids-limit=-1",
        "--user=root:root",
    ])

    # Namespace sharing
    if not opts.unshare_ipc:
        cmd.append("--ipc=host")
    if not opts.unshare_netns:
        cmd.append("--network=host")
    if not opts.unshare_process:
        cmd.append("--pid=host")

    # Labels and environment
    cmd.extend([
        "--label=manager=distrobox",
        f"--label=distrobox.unshare_groups={1 if opts.unshare_groups else 0}",
        f"--env=SHELL={Path(shell).name}",
        f"--env=HOME={container_home}",
        f"--env=container={manager.name}",
        "--env=TERMINFO_DIRS=/usr/share/terminfo:/run/host/usr/share/terminfo",
        f"--env=CONTAINER_ID={opts.name}",
    ])

    # Volume mounts
    cmd.append("--volume=/tmp:/tmp:rslave")
    cmd.append(f"--volume={entrypoint_path}:/usr/bin/entrypoint:ro")
    cmd.append(f"--volume={export_path}:/usr/bin/distrobox-export:ro")
    if hostexec_path:
        cmd.append(f"--volume={hostexec_path}:/usr/bin/distrobox-host-exec:ro")
    cmd.append(f"--volume={home}:{home}:rslave")

    # Handle root filesystem mounting based on podman+runc
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

    # Device and sysfs mounts
    if not opts.unshare_devsys:
        cmd.append("--volume=/dev:/dev:rslave")
        cmd.append("--volume=/sys:/sys:rslave")

    # Init system support
    if opts.init and manager.is_docker:
        cmd.append("--cgroupns=host")
    if opts.init and not manager.is_podman:
        cmd.extend([
            "--stop-signal=SIGRTMIN+3",
            "--mount=type=tmpfs,destination=/run",
            "--mount=type=tmpfs,destination=/run/lock",
            "--mount=type=tmpfs,destination=/var/lib/journal",
        ])

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

    # RHEL subscription files
    rhel_files = [
        ("/etc/pki/entitlement/", "/run/secrets/etc-pki-entitlement", "ro"),
        ("/etc/rhsm/", "/run/secrets/rhsm", "ro"),
        ("/etc/yum.repos.d/redhat.repo", "/run/secrets/redhat.repo", "ro"),
    ]
    for src, dst, mode in rhel_files:
        if file_exists(src):
            cmd.append(f"--volume={src}:{dst}:{mode}")

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

    # Network config files
    if not opts.unshare_netns:
        for net_file in ["/etc/hosts", "/etc/resolv.conf"]:
            if file_exists(net_file):
                cmd.append(f"--volume={net_file}:{net_file}:ro")
        # Only mount /etc/hostname if not using custom hostname
        if opts.hostname == get_hostname() and file_exists("/etc/hostname"):
            cmd.append("--volume=/etc/hostname:/etc/hostname:ro")

    # Podman-specific options
    if manager.is_podman:
        if manager.has_crun():
            cmd.append("--runtime=crun")
        cmd.extend([
            "--annotation=run.oci.keep_original_groups=1",
            "--ulimit=host",
        ])
        if opts.init:
            cmd.append("--systemd=always")
        if not config.rootful:
            userns = "--userns=keep-id"
            # Check for keep-id:size support
            if not config.userns_nolimit and manager.supports_keepid_size(opts.image):
                userns += ":size=65536"
            cmd.append(userns)

    # nopasswd flag
    if opts.nopasswd:
        cmd.append("--volume=/dev/null:/run/.nopasswd:ro")

    # Additional volumes
    for volume in opts.additional_volumes:
        cmd.append(f"--volume={volume}")

    # Additional flags
    for flag in opts.additional_flags:
        cmd.append(flag)

    # Entrypoint and image
    cmd.append("--entrypoint=/usr/bin/entrypoint")
    cmd.append(opts.image)

    # Entrypoint arguments (use space-separated format for distrobox-init compatibility)
    cmd.extend([
        "--verbose",
        "--name", user,
        "--user", str(uid),
        "--group", str(gid),
        "--home", opts.custom_home or home,
        "--init", str(1 if opts.init else 0),
        "--nvidia", str(1 if opts.nvidia else 0),
        "--pre-init-hooks", opts.pre_init_hooks,
        "--additional-packages", opts.additional_packages,
        "--",
        opts.init_hooks,
    ])

    return cmd


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-create command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
        print(
            f"Running {sys.argv[0]} via SUDO/DOAS is not supported.",
            file=sys.stderr,
        )
        print(
            f"Instead, please try running:\n  {sys.argv[0]} --root",
            file=sys.stderr,
        )
        return 1

    # Parse arguments
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Handle --compatibility flag early
    if parsed.compatibility:
        return show_compatibility()

    # Load config
    config = Config.load()

    # Apply command line overrides
    if parsed.root:
        config.rootful = True
    if parsed.verbose:
        config.verbose = True
    if parsed.yes or parsed.pull:
        config.non_interactive = True

    # Build create options
    opts = CreateOptions()

    # Handle image/name from various sources
    opts.clone = parsed.clone or ""

    if parsed.image:
        opts.image = parsed.image
    elif config.container_image:
        opts.image = config.container_image
    elif not opts.clone:
        opts.image = DEFAULT_IMAGE

    # Name handling
    if parsed.name:
        opts.name = parsed.name
    elif parsed.name_positional:
        opts.name = parsed.name_positional
    elif config.container_name:
        opts.name = config.container_name
    elif opts.image == DEFAULT_IMAGE:
        opts.name = DEFAULT_NAME
    elif opts.image:
        opts.name = derive_container_name(opts.image)

    # Hostname
    opts.hostname = parsed.hostname or config.container_hostname or get_hostname()
    if parsed.unshare_netns:
        opts.hostname = f"{opts.name}.{opts.hostname}"

    # Validate hostname
    if not validate_hostname(opts.hostname):
        print(f"Error: Invalid hostname '{opts.hostname}', longer than 64 characters", file=sys.stderr)
        print("Use --hostname argument to set it manually", file=sys.stderr)
        return 1

    # Custom home
    if parsed.home:
        opts.custom_home = remove_trailing_slashes(parsed.home)
    elif config.container_custom_home:
        opts.custom_home = config.container_custom_home
    elif config.container_home_prefix:
        opts.custom_home = f"{config.container_home_prefix}/{opts.name}"

    # Other options
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

    # Unshare options
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

    # Detect container manager
    manager = detect_container_manager(
        preferred=config.container_manager,
        verbose=config.verbose,
        rootful=config.rootful,
        sudo_program=config.sudo_program,
    )

    # Handle clone
    if opts.clone:
        if not manager.is_podman and not manager.is_docker:
            print("Error: clone is only supported with docker and podman", file=sys.stderr)
            return 127
        clone_image = get_clone_image(manager, opts.clone)
        if not clone_image:
            return 1
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
        print("To enter, run:\n")
        if config.rootful and os.getuid() != 0:
            print(f"distrobox enter --root {opts.name}\n")
        else:
            print(f"distrobox enter {opts.name}\n")
        return 0

    # Check/pull image
    if opts.pull or not manager.image_exists(opts.image):
        if not config.non_interactive and not opts.pull:
            print(f"Image {opts.image} not found.", file=sys.stderr)
            if not prompt_yes_no("Do you want to pull the image now?"):
                print(f"Next time, run: {manager.name} pull {opts.image}", file=sys.stderr)
                return 0

        if not manager.pull(opts.image, opts.platform or None):
            print(f"Failed to pull {opts.image}", file=sys.stderr)
            return 1

    # Generate and run create command
    print(f"Creating '{opts.name}' using image {opts.image}\t", end="", file=sys.stderr)

    cmd = generate_create_command(manager, opts, config)
    result = manager.run(*cmd, capture_output=True)

    if result.returncode == 0:
        print_ok()
        print(f"Distrobox '{opts.name}' successfully created.", file=sys.stderr)
        print("To enter, run:\n")
        if config.rootful and os.getuid() != 0:
            print(f"distrobox enter --root {opts.name}\n")
        else:
            print(f"distrobox enter {opts.name}\n")

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


if __name__ == "__main__":
    sys.exit(run())
