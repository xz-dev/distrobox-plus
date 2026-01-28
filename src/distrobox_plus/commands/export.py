"""distrobox-export command implementation.

Exports apps, binaries or services from container to host.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ..config import VERSION, get_user_info


# Base dependencies required by the original script
BASE_DEPENDENCIES = ("basename", "find", "grep", "sed")

# Sudo askpass script for rootful containers
SUDO_ASKPASS_SCRIPT = """\
#!/bin/sh
if command -v zenity 2>&1 > /dev/null; then
	zenity --password
elif command -v kdialog 2>&1 > /dev/null; then
	kdialog --password 'A password is required...'
else
	exit 127
fi"""


def _get_container_name() -> str:
    """Get the current container name.

    Matches original: CONTAINER_ID or from /run/.containerenv
    """
    # First try CONTAINER_ID environment variable
    container_name = os.environ.get("CONTAINER_ID", "")
    if container_name:
        return container_name

    # Then try to read from /run/.containerenv
    containerenv = Path("/run/.containerenv")
    if containerenv.exists():
        try:
            content = containerenv.read_text()
            for line in content.splitlines():
                if line.startswith("name="):
                    # Extract value and remove quotes
                    value = line.split("=", 1)[1]
                    return value.strip('"')
        except OSError:
            pass

    return ""


def _get_host_home() -> str:
    """Get the host home directory.

    Uses DISTROBOX_HOST_HOME if defined, else HOME.
    """
    return os.environ.get("DISTROBOX_HOST_HOME", os.environ.get("HOME", ""))


def _get_dest_path(host_home: str) -> str:
    """Get the destination path for exported binaries.

    Uses DISTROBOX_EXPORT_PATH if defined, else host_home/.local/bin.
    """
    return os.environ.get("DISTROBOX_EXPORT_PATH", f"{host_home}/.local/bin")


def _get_distrobox_enter_path() -> str:
    """Get the distrobox-enter path.

    Uses DISTROBOX_ENTER_PATH if defined, else 'distrobox-enter'.
    """
    return os.environ.get("DISTROBOX_ENTER_PATH", "distrobox-enter")


def _check_dependencies() -> bool:
    """Check if all base dependencies are available.

    Returns:
        True if all dependencies are available
    """
    for dep in BASE_DEPENDENCIES:
        if not shutil.which(dep):
            print(f"Missing dependency: {dep}", file=sys.stderr)
            return False
    return True


def _check_in_container() -> bool:
    """Check if running inside a container.

    Returns:
        True if inside a container
    """
    if Path("/run/.containerenv").exists():
        return True
    if Path("/.dockerenv").exists():
        return True
    if os.environ.get("container"):
        return True
    return False


def _is_rootful_container() -> bool:
    """Check if running in a rootful container.

    Returns:
        True if rootful container (rootless=0 in /run/.containerenv)
    """
    containerenv = Path("/run/.containerenv")
    if containerenv.exists():
        try:
            content = containerenv.read_text()
            if "rootless=0" in content:
                return True
        except OSError:
            pass
    return False


def _setup_sudo_askpass(dest_path: str) -> None:
    """Set up sudo askpass script for rootful containers."""
    askpass_path = Path(dest_path) / "distrobox_sudo_askpass"
    if not askpass_path.exists():
        try:
            askpass_path.write_text(SUDO_ASKPASS_SCRIPT)
            askpass_path.chmod(0o755)
        except OSError:
            pass


def _filter_enter_flags(enter_flags: str) -> str:
    """Filter enter_flags and remove redundant options.

    Removes --root/-r and --name/-n flags as they are set automatically.
    """
    if not enter_flags:
        return ""

    parts = enter_flags.split()
    filtered: list[str] = []
    skip_next = False

    for i, part in enumerate(parts):
        if skip_next:
            skip_next = False
            continue

        if part in ("--root", "-r"):
            print(
                f"Warning: {part} argument will be set automatically and should be removed.",
                file=sys.stderr,
            )
        elif part in ("--name", "-n"):
            print(
                f"Warning: {part} argument will be set automatically and should be removed.",
                file=sys.stderr,
            )
            skip_next = True
        else:
            filtered.append(part)

    return " ".join(filtered)


def _get_sudo_prefix(is_sudo: bool) -> str:
    """Get the sudo prefix for commands.

    Args:
        is_sudo: Whether to use sudo

    Returns:
        Sudo prefix string
    """
    if not is_sudo:
        return ""

    sudo_prefix = "sudo -S"
    # Test if sudo -S works
    try:
        result = subprocess.run(
            ["sudo", "-S", "test"],
            capture_output=True,
            timeout=1,
        )
        if result.returncode != 0:
            sudo_prefix = "sudo"
    except (subprocess.TimeoutExpired, OSError):
        sudo_prefix = "sudo"

    # Edge case for systems with doas
    if shutil.which("doas"):
        sudo_prefix = "doas"

    # Edge case for systems without sudo
    if shutil.which("su-exec"):
        sudo_prefix = "su-exec root"

    return sudo_prefix


def _build_container_command_suffix(
    exported_bin: str,
    extra_flags: str,
    sudo_prefix: str,
) -> str:
    """Build the container command suffix.

    Matches original shell script behavior.
    """
    if sudo_prefix in ("doas", "su-exec root"):
        return f'sh -l -c "\'{exported_bin}\' {extra_flags} $@"'
    return f"'{exported_bin}' {extra_flags} \"$@\""


def _build_container_command_prefix(
    container_name: str,
    enter_flags: str,
    rootful: str,
    sudo_prefix: str,
    sudo_askpass_path: str,
) -> str:
    """Build the container command prefix.

    Args:
        container_name: Name of the container
        enter_flags: Extra flags for distrobox-enter
        rootful: --root flag if rootful container
        sudo_prefix: Sudo command prefix
        sudo_askpass_path: Path to sudo askpass script

    Returns:
        Command prefix string
    """
    distrobox_enter = _get_distrobox_enter_path()
    prefix = f"{distrobox_enter} {rootful} -n {container_name} {enter_flags} -- {sudo_prefix} "

    if rootful:
        prefix = (
            f'env SUDO_ASKPASS="{sudo_askpass_path}" '
            f'DBX_SUDO_PROGRAM="sudo --askpass" {prefix}'
        )

    return prefix


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-export."""
    epilog = """\
Usage:

    distrobox-export --app mpv [--extra-flags "flags"] [--enter-flags "flags"] [--delete] [--sudo]
    distrobox-export --bin /path/to/bin [--export-path ~/.local/bin] [--extra-flags "flags"] [--enter-flags "flags"] [--delete] [--sudo]
"""
    parser = argparse.ArgumentParser(
        prog="distrobox-export",
        description=f"distrobox version: {VERSION}\n\n"
        "Application and binary exporter from container to host.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-a", "--app",
        dest="exported_app",
        help="name of the application to export or absolute path to desktopfile to export",
    )
    parser.add_argument(
        "-b", "--bin",
        dest="exported_bin",
        help="absolute path of the binary to export",
    )
    parser.add_argument(
        "--list-apps",
        action="store_true",
        help="list applications exported from this container",
    )
    parser.add_argument(
        "--list-binaries",
        action="store_true",
        help="list binaries exported from this container, use -ep to specify custom paths to search",
    )
    parser.add_argument(
        "-d", "--delete",
        action="store_true",
        dest="exported_delete",
        help="delete exported application or binary",
    )
    parser.add_argument(
        "-el", "--export-label",
        dest="exported_app_label",
        help='label to add to exported application name. Use "none" to disable. '
        "Defaults to (on $container_name)",
    )
    parser.add_argument(
        "-ep", "--export-path",
        dest="dest_path",
        help="path where to export the binary",
    )
    parser.add_argument(
        "-ef", "--extra-flags",
        help="extra flags to add to the command",
    )
    parser.add_argument(
        "-nf", "--enter-flags",
        help="flags to add to distrobox-enter",
    )
    parser.add_argument(
        "-S", "--sudo",
        action="store_true",
        dest="is_sudo",
        help="specify if the exported item should be run as sudo",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="show more verbosity",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"distrobox: {VERSION}",
    )

    return parser


def _generate_script(
    container_name: str,
    exported_bin: str,
    dest_path: str,
    rootful: str,
    enter_flags: str,
    sudo_prefix: str,
    extra_flags: str,
) -> str:
    """Generate a wrapper script for the exported binary.

    Matches original generate_script() function.
    """
    distrobox_enter = _get_distrobox_enter_path()
    container_command_suffix = _build_container_command_suffix(
        exported_bin, extra_flags, sudo_prefix
    )
    basename = Path(exported_bin).name

    return f"""\
#!/bin/sh
# distrobox_binary
# name: {container_name}
if [ -z "${{CONTAINER_ID}}" ]; then
	exec "{distrobox_enter}" {rootful} -n {container_name} {enter_flags} -- {sudo_prefix} {container_command_suffix}
elif [ -n "${{CONTAINER_ID}}" ] && [ "${{CONTAINER_ID}}" != "{container_name}" ]; then
	exec distrobox-host-exec '{dest_path}/{basename}' "$@"
else
	exec {sudo_prefix} '{exported_bin}' "$@"
fi
"""


def _export_binary(
    container_name: str,
    exported_bin: str,
    dest_path: str,
    exported_delete: bool,
    rootful: str,
    enter_flags: str,
    sudo_prefix: str,
    extra_flags: str,
) -> int:
    """Export a binary to the host.

    Args:
        container_name: Name of the container
        exported_bin: Path to binary to export
        dest_path: Destination path
        exported_delete: Whether to delete the export
        rootful: --root flag if rootful
        enter_flags: Extra flags for distrobox-enter
        sudo_prefix: Sudo command prefix
        extra_flags: Extra flags for the command

    Returns:
        Exit code
    """
    # Ensure the binary we're exporting is installed
    if not Path(exported_bin).is_file():
        print(f"Error: cannot find {exported_bin}.", file=sys.stderr)
        return 127

    # Generate dest_file path
    dest_file = Path(dest_path) / Path(exported_bin).name

    # Create the binary destination path if it doesn't exist
    Path(dest_path).mkdir(parents=True, exist_ok=True)

    # If we're deleting it, just do it and exit
    if exported_delete:
        # Ensure it's a distrobox exported binary
        if dest_file.exists():
            try:
                content = dest_file.read_text()
                if "distrobox_binary" not in content:
                    print(f"Error: {exported_bin} is not exported.", file=sys.stderr)
                    return 1
            except OSError:
                print(f"Error: {exported_bin} is not exported.", file=sys.stderr)
                return 1

            try:
                dest_file.unlink()
                print(
                    f"{exported_bin} from {container_name} removed successfully from {dest_path}.\nOK!"
                )
                return 0
            except OSError:
                return 1
        else:
            print(f"Error: {exported_bin} is not exported.", file=sys.stderr)
            return 1

    # Test if we have writing rights on the file
    try:
        dest_file.touch()
    except OSError:
        print(f"Error: cannot create destination file {dest_file}.", file=sys.stderr)
        return 1

    # Create the script from template and write to file
    try:
        script = _generate_script(
            container_name,
            exported_bin,
            dest_path,
            rootful,
            enter_flags,
            sudo_prefix,
            extra_flags,
        )
        dest_file.write_text(script)
        dest_file.chmod(0o755)
        print(
            f"{exported_bin} from {container_name} exported successfully in {dest_path}.\nOK!"
        )
        return 0
    except OSError:
        return 3


def _find_desktop_files(exported_app: str, canon_dirs: list[str]) -> list[str]:
    """Find desktop files for the exported application.

    Args:
        exported_app: Application name or path to desktop file
        canon_dirs: List of canonical directories to search

    Returns:
        List of desktop file paths
    """
    # In case we're explicitly going for a full desktopfile path
    if Path(exported_app).exists():
        return [exported_app]

    desktop_files: list[str] = []
    distrobox_enter = _get_distrobox_enter_path()

    for canon_dir in canon_dirs:
        if not Path(canon_dir).is_dir():
            continue

        # Find all desktop files
        for desktop_file in Path(canon_dir).glob("*.desktop"):
            try:
                content = desktop_file.read_text()
                # Check if it matches the exported app (by Exec or Name)
                if (
                    f"Exec=.*{exported_app}.*" in content
                    or re.search(f"Exec=.*{re.escape(exported_app)}.*", content)
                    or re.search(f"Name=.*{re.escape(exported_app)}.*", content)
                ):
                    # Skip already exported apps
                    if distrobox_enter not in content and "distrobox.*enter" not in content:
                        desktop_files.append(str(desktop_file))
            except OSError:
                continue

        # Also check symlinks
        for desktop_file in Path(canon_dir).iterdir():
            if desktop_file.suffix == ".desktop" and desktop_file.is_symlink():
                try:
                    content = desktop_file.read_text()
                    if (
                        re.search(f"Exec=.*{re.escape(exported_app)}.*", content)
                        or re.search(f"Name=.*{re.escape(exported_app)}.*", content)
                    ):
                        if distrobox_enter not in content and "distrobox.*enter" not in content:
                            if str(desktop_file) not in desktop_files:
                                desktop_files.append(str(desktop_file))
                except OSError:
                    continue

    return desktop_files


def _get_canonical_dirs() -> list[str]:
    """Get canonical directories for desktop files.

    Returns:
        List of canonical directory paths
    """
    canon_dirs: list[str] = []
    xdg_data_dirs = os.environ.get("XDG_DATA_DIRS", "")

    if xdg_data_dirs:
        for xdg_data_dir in xdg_data_dirs.split(":"):
            app_dir = f"{xdg_data_dir}/applications"
            if Path(app_dir).is_dir():
                canon_dirs.append(app_dir)
    else:
        if Path("/usr/share/applications").is_dir():
            canon_dirs.append("/usr/share/applications")
        if Path("/usr/local/share/applications").is_dir():
            canon_dirs.append("/usr/local/share/applications")
        if Path("/var/lib/flatpak/exports/share/applications").is_dir():
            canon_dirs.append("/var/lib/flatpak/exports/share/applications")

    xdg_data_home = os.environ.get("XDG_DATA_HOME", "")
    if xdg_data_home:
        app_dir = f"{xdg_data_home}/applications"
        if Path(app_dir).is_dir():
            canon_dirs.append(app_dir)
    else:
        home = os.environ.get("HOME", "")
        if home and Path(f"{home}/.local/share/applications").is_dir():
            canon_dirs.append(f"{home}/.local/share/applications")

    return canon_dirs


def _find_icon_files(desktop_files: list[str]) -> list[str]:
    """Find icon files for the desktop files.

    Args:
        desktop_files: List of desktop file paths

    Returns:
        List of icon file paths
    """
    icon_files: list[str] = []
    icon_search_dirs = [
        "/usr/share/icons",
        "/usr/share/pixmaps",
        "/var/lib/flatpak/exports/share/icons",
    ]

    for desktop_file in desktop_files:
        try:
            content = Path(desktop_file).read_text()
            for line in content.splitlines():
                if line.startswith("Icon="):
                    icon_name = line.split("=", 1)[1].strip()

                    # If it's an absolute path
                    if icon_name.startswith("/") and Path(icon_name).exists():
                        icon_files.append(icon_name)
                    else:
                        # Search for the icon in canonical paths
                        for search_dir in icon_search_dirs:
                            if not Path(search_dir).is_dir():
                                continue
                            for icon_path in Path(search_dir).rglob(f"*{icon_name}*"):
                                if str(icon_path) not in icon_files:
                                    icon_files.append(str(icon_path))
        except OSError:
            continue

    return icon_files


def _export_application(
    container_name: str,
    exported_app: str,
    exported_app_label: str,
    exported_delete: bool,
    container_command_prefix: str,
    extra_flags: str,
    host_home: str,
) -> int:
    """Export an application to the host.

    Args:
        container_name: Name of the container
        exported_app: Application name or path
        exported_app_label: Label to add to application name
        exported_delete: Whether to delete the export
        container_command_prefix: Command prefix for container execution
        extra_flags: Extra flags for the command
        host_home: Host home directory

    Returns:
        Exit code
    """
    canon_dirs = _get_canonical_dirs()
    desktop_files = _find_desktop_files(exported_app, canon_dirs)

    # Ensure the app we're exporting is installed
    if not desktop_files:
        print("Error: cannot find any desktop files.", file=sys.stderr)
        print("Error: trying to export a non-installed application.", file=sys.stderr)
        return 127

    # Find icons
    icon_files = _find_icon_files(desktop_files)

    # Create applications dir if not existing
    apps_dir = Path(f"/run/host{host_home}/.local/share/applications")
    apps_dir.mkdir(parents=True, exist_ok=True)

    # Copy icons in home directory
    icon_file_absolute_path = ""
    for icon_file in icon_files:
        # Replace canonical paths with equivalent paths in HOME
        icon_home_directory = (
            os.path.dirname(icon_file)
            .replace("/usr/share/", f"/run/host/{host_home}/.local/share/")
            .replace("/var/lib/flatpak/exports/share", f"/run/host/{host_home}/.local/share")
            .replace("pixmaps", "icons")
        )

        # Check if we're exporting an icon which is not in a canonical path
        if icon_home_directory == os.path.dirname(icon_file):
            icon_home_directory = f"{host_home}/.local/share/icons/"
            icon_file_absolute_path = f"{icon_home_directory}{os.path.basename(icon_file)}"

        # Check if we're exporting or deleting
        if exported_delete:
            # Remove icon
            try:
                icon_to_remove = Path(icon_home_directory) / os.path.basename(icon_file)
                if icon_to_remove.exists():
                    icon_to_remove.unlink()
            except OSError:
                pass
            continue

        # Export the application's icons
        Path(icon_home_directory).mkdir(parents=True, exist_ok=True)
        dest_icon = Path(icon_home_directory) / os.path.basename(icon_file)
        if not dest_icon.exists():
            try:
                real_icon = Path(icon_file).resolve()
                if real_icon.exists():
                    shutil.copy2(str(real_icon), str(dest_icon))
            except OSError:
                pass

    # Create desktop files for the distrobox
    for desktop_file in desktop_files:
        desktop_original_file = os.path.basename(desktop_file)
        desktop_home_file = f"{container_name}-{desktop_original_file}"
        dest_desktop = apps_dir / desktop_home_file

        # Check if we're exporting or deleting
        if exported_delete:
            try:
                (apps_dir / desktop_original_file).unlink(missing_ok=True)
                dest_desktop.unlink(missing_ok=True)
            except OSError:
                pass
            continue

        # Read and modify desktop file
        try:
            content = Path(desktop_file).read_text()

            # Add command_prefix to Exec lines
            content = re.sub(
                r"^Exec=(.*)$",
                f"Exec={container_command_prefix} \\1 ",
                content,
                flags=re.MULTILINE,
            )

            # Add extra flags before % arguments
            if extra_flags:
                content = re.sub(
                    r"(%.*)",
                    f"{extra_flags} \\1",
                    content,
                )

            # Remove TryExec and DBusActivatable
            content = re.sub(r"^TryExec=.*\n?", "", content, flags=re.MULTILINE)
            content = re.sub(r"^DBusActivatable=true\n?", "", content, flags=re.MULTILINE)

            # Add label to Name
            content = re.sub(
                r"^(Name.*)$",
                f"\\1{exported_app_label}",
                content,
                flags=re.MULTILINE,
            )

            dest_desktop.write_text(content)

            # Add StartupWMClass if not present
            if "StartupWMClass" not in content:
                with open(dest_desktop, "a") as f:
                    f.write(f"StartupWMClass={exported_app}\n")

            # Fix icon paths
            if icon_file_absolute_path:
                content = dest_desktop.read_text()
                content = re.sub(
                    r"^Icon=.*$",
                    f"Icon={icon_file_absolute_path}",
                    content,
                    flags=re.MULTILINE,
                )
                dest_desktop.write_text(content)
            else:
                content = dest_desktop.read_text()
                content = content.replace(
                    "Icon=/usr/share/",
                    f"Icon=/run/host{host_home}/.local/share/",
                )
                content = content.replace("pixmaps", "icons")
                dest_desktop.write_text(content)

        except OSError as e:
            print(f"Error processing {desktop_file}: {e}", file=sys.stderr)
            continue

    # Update desktop database
    try:
        subprocess.run(
            [
                "/usr/bin/distrobox-host-exec",
                "--yes",
                "update-desktop-database",
                f"{host_home}/.local/share/applications",
            ],
            capture_output=True,
        )
    except OSError:
        pass

    if exported_delete:
        print(f"Application {exported_app} successfully un-exported.\nOK!")
        print(f"{exported_app} will disappear from your applications list in a few seconds.")
    else:
        print(f"Application {exported_app} successfully exported.\nOK!")
        print(f"{exported_app} will appear in your applications list in a few seconds.")

    return 0


def _list_exported_applications(host_home: str, container_id: str) -> int:
    """List exported applications from this container.

    Args:
        host_home: Host home directory
        container_id: Container ID

    Returns:
        Exit code
    """
    distrobox_enter = _get_distrobox_enter_path()
    apps_dir = Path(f"/run/host{host_home}/.local/share/applications")

    if not apps_dir.is_dir():
        return 0

    for desktop_file in apps_dir.glob("*.desktop"):
        try:
            content = desktop_file.read_text()
            # Check if it's a distrobox exported app
            if distrobox_enter in content or re.search(r"distrobox.*enter", content):
                # Check if it's from this container
                if container_id in str(desktop_file):
                    # Get app name
                    name = ""
                    for line in content.splitlines():
                        if line.startswith("Name="):
                            name = line.split("=", 1)[1]
                            # Remove label
                            name = re.sub(r"\(.*\)", "", name).strip()
                            break
                    print(f"{name:<20} | {desktop_file}")
        except OSError:
            continue

    return 0


def _list_exported_binaries(dest_path: str, container_id: str) -> int:
    """List exported binaries from this container.

    Args:
        dest_path: Path to search for binaries
        container_id: Container ID

    Returns:
        Exit code
    """
    dest_dir = Path(dest_path)
    if not dest_dir.is_dir():
        return 0

    for binary_file in dest_dir.iterdir():
        if not binary_file.is_file():
            continue

        try:
            content = binary_file.read_text()
            # Check if it's a distrobox exported binary
            if "# distrobox_binary" in content:
                # Check if it's from this container
                if f"# name: {container_id}" in content or f"name: {container_id}" in content:
                    # Get original binary name
                    for line in content.splitlines():
                        if "exec" in line.lower() and "'" in line:
                            # Extract the binary path
                            match = re.search(r"exec\s+\S*\s*'([^']+)'", line, re.IGNORECASE)
                            if match:
                                name = match.group(1)
                                print(f"{name:<20} | {binary_file}")
                                break
        except OSError:
            continue

    return 0


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-export command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    if args is None:
        args = sys.argv[1:]

    # Check dependencies
    if not _check_dependencies():
        return 127

    # Parse arguments
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Get environment info
    _, _, _ = get_user_info()
    host_home = _get_host_home()
    dest_path = parsed.dest_path or _get_dest_path(host_home)
    container_name = _get_container_name()

    # Ensure we can write stuff there
    Path(dest_path).mkdir(parents=True, exist_ok=True)

    # Check we're running inside a container and not on the host
    if not _check_in_container():
        print(
            f"You must run {Path(sys.argv[0]).name} inside a container!",
            file=sys.stderr,
        )
        return 126

    # Check if we're in a rootful container
    rootful = ""
    if _is_rootful_container():
        rootful = "--root"
        _setup_sudo_askpass(dest_path)

    # We're working with HOME, so we must run as USER, not as root
    if os.getuid() == 0:
        print(
            f"You must not run {Path(sys.argv[0]).name} as root!",
            file=sys.stderr,
        )
        return 1

    # Determine export action
    export_action = ""
    if parsed.exported_app:
        export_action = "app"
    elif parsed.exported_bin:
        export_action = "bin"
    elif parsed.list_apps:
        export_action = "list-apps"
    elif parsed.list_binaries:
        export_action = "list-binaries"

    # Ensure we're not receiving more than one action at time
    actions_count = sum([
        bool(parsed.exported_app),
        bool(parsed.exported_bin),
        parsed.list_apps,
        parsed.list_binaries,
    ])
    if actions_count > 1:
        print("Error: Invalid arguments, choose only one action below.", file=sys.stderr)
        print("Error: You can only export one thing at time.", file=sys.stderr)
        return 2

    # Filter enter_flags
    enter_flags = _filter_enter_flags(parsed.enter_flags or "")

    # Get sudo prefix
    sudo_prefix = _get_sudo_prefix(parsed.is_sudo)

    # Build exported app label
    exported_app_label = parsed.exported_app_label or ""
    if not exported_app_label:
        exported_app_label = f" (on {container_name})"
    elif exported_app_label == "none":
        exported_app_label = ""
    else:
        # Add a leading space so that we can have "NAME LABEL" in the entry
        exported_app_label = f" {exported_app_label}"

    # Build container command prefix for app export
    sudo_askpass_path = f"{dest_path}/distrobox_sudo_askpass"
    container_command_prefix = _build_container_command_prefix(
        container_name,
        enter_flags,
        rootful,
        sudo_prefix,
        sudo_askpass_path,
    )

    # Execute action
    container_id = os.environ.get("CONTAINER_ID", container_name)

    if export_action == "app":
        return _export_application(
            container_name,
            parsed.exported_app,
            exported_app_label,
            parsed.exported_delete,
            container_command_prefix,
            parsed.extra_flags or "",
            host_home,
        )
    elif export_action == "bin":
        return _export_binary(
            container_name,
            parsed.exported_bin,
            dest_path,
            parsed.exported_delete,
            rootful,
            enter_flags,
            sudo_prefix,
            parsed.extra_flags or "",
        )
    elif export_action == "list-apps":
        return _list_exported_applications(host_home, container_id)
    elif export_action == "list-binaries":
        return _list_exported_binaries(dest_path, container_id)
    else:
        print("Invalid arguments, choose an action below.", file=sys.stderr)
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(run())
