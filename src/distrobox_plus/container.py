"""Container manager abstraction for distrobox-plus.

Provides a unified interface for podman, docker, and lilipod.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

SUPPORTED_MANAGERS = ("podman", "podman-launcher", "docker", "lilipod")


@dataclass
class ContainerManager:
    """Container manager wrapper for podman/docker/lilipod.

    Provides a consistent interface for container operations across
    different container managers.
    """
    name: str
    path: str
    verbose: bool = False
    rootful: bool = False
    sudo_program: str = "sudo"

    # Cached command prefix
    _cmd_prefix: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Build command prefix."""
        self._build_cmd_prefix()

    def _build_cmd_prefix(self) -> None:
        """Build the command prefix including sudo if needed."""
        self._cmd_prefix = []
        if self.rootful:
            self._cmd_prefix.append(self.sudo_program)
        self._cmd_prefix.append(self.path)
        if self.verbose:
            self._cmd_prefix.append("--log-level")
            self._cmd_prefix.append("debug")

    def run(
        self,
        *args: str,
        capture_output: bool = True,
        check: bool = False,
        text: bool = True,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        """Run a container manager command.

        Args:
            *args: Command arguments to pass to the container manager
            capture_output: Capture stdout/stderr
            check: Raise exception on non-zero exit
            text: Return text instead of bytes
            **kwargs: Additional arguments for subprocess.run

        Returns:
            CompletedProcess with the result
        """
        cmd = [*self._cmd_prefix, *args]
        return subprocess.run(
            cmd,
            capture_output=capture_output,
            check=check,
            text=text,
            **kwargs,
        )

    def run_interactive(self, *args: str) -> int:
        """Run a container manager command interactively.

        Passes through stdin/stdout/stderr without capturing.

        Args:
            *args: Command arguments to pass to the container manager

        Returns:
            Exit code of the command
        """
        cmd = [*self._cmd_prefix, *args]
        result = subprocess.run(cmd)
        return result.returncode

    def exec_replace(self, *args: str) -> None:
        """Replace current process with container manager command.

        Uses os.execvp to replace the current process.

        Args:
            *args: Command arguments to pass to the container manager
        """
        import os
        cmd = [*self._cmd_prefix, *args]
        os.execvp(cmd[0], cmd)

    def inspect(
        self,
        name: str,
        type_: str = "container",
        format_: str | None = None,
    ) -> dict[str, Any] | str | None:
        """Inspect a container or image.

        Args:
            name: Container or image name
            type_: Type to inspect ("container" or "image")
            format_: Go template format string, or None for full JSON

        Returns:
            Parsed JSON dict if no format, formatted string if format specified,
            None if container doesn't exist
        """
        args = ["inspect", "--type", type_]
        if format_:
            args.extend(["--format", format_])
        args.append(name)

        result = self.run(*args)
        if result.returncode != 0:
            return None

        if format_:
            return result.stdout.strip()

        try:
            data = json.loads(result.stdout)
            return data[0] if data else None
        except (json.JSONDecodeError, IndexError):
            return None

    def exists(self, name: str) -> bool:
        """Check if a container exists.

        Args:
            name: Container name

        Returns:
            True if container exists
        """
        return self.inspect(name) is not None

    def is_running(self, name: str) -> bool:
        """Check if a container is running.

        Args:
            name: Container name

        Returns:
            True if container is running
        """
        status = self.get_status(name)
        return status in ("running", "Up")

    def get_status(self, name: str) -> str | None:
        """Get container status.

        Args:
            name: Container name

        Returns:
            Status string or None if container doesn't exist
        """
        result = self.inspect(name, format_="{{.State.Status}}")
        return result if isinstance(result, str) else None

    def ps(
        self,
        all_: bool = True,
        format_: str | None = None,
        no_trunc: bool = False,
    ) -> str:
        """List containers.

        Args:
            all_: Include stopped containers
            format_: Go template format string
            no_trunc: Don't truncate output

        Returns:
            Command output as string
        """
        args = ["ps"]
        if all_:
            args.append("-a")
        if no_trunc:
            args.append("--no-trunc")
        if format_:
            args.extend(["--format", format_])

        result = self.run(*args)
        return result.stdout

    def start(self, name: str) -> bool:
        """Start a container.

        Args:
            name: Container name

        Returns:
            True if successful
        """
        result = self.run("start", name)
        return result.returncode == 0

    def stop(self, name: str) -> bool:
        """Stop a container.

        Args:
            name: Container name

        Returns:
            True if successful
        """
        result = self.run("stop", name)
        return result.returncode == 0

    def rm(self, name: str, force: bool = False, volumes: bool = True) -> bool:
        """Remove a container.

        Args:
            name: Container name
            force: Force removal
            volumes: Remove volumes

        Returns:
            True if successful
        """
        args = ["rm"]
        if force:
            args.append("--force")
        if volumes:
            args.append("--volumes")
        args.append(name)

        result = self.run(*args)
        return result.returncode == 0

    def pull(self, image: str, platform: str | None = None) -> bool:
        """Pull an image.

        Args:
            image: Image name
            platform: Platform specification (e.g., linux/arm64)

        Returns:
            True if successful
        """
        args = ["pull"]
        if platform:
            args.append(f"--platform={platform}")
        args.append(image)

        # Don't capture output - let it show progress
        result = subprocess.run([*self._cmd_prefix, *args])
        return result.returncode == 0

    def image_exists(self, image: str) -> bool:
        """Check if an image exists locally.

        Args:
            image: Image name

        Returns:
            True if image exists
        """
        return self.inspect(image, type_="image") is not None

    def logs(self, name: str, since: str | None = None, follow: bool = False) -> str:
        """Get container logs.

        Args:
            name: Container name
            since: Only show logs since timestamp
            follow: Follow log output

        Returns:
            Log output
        """
        args = ["logs"]
        if since:
            args.extend(["--since", since])
        if follow:
            args.append("-f")
        args.append(name)

        result = self.run(*args)
        return result.stdout + result.stderr

    def commit(self, container: str, tag: str) -> bool:
        """Commit a container to an image.

        Args:
            container: Container name or ID
            tag: Image tag for the commit

        Returns:
            True if successful
        """
        result = self.run("container", "commit", container, tag)
        return result.returncode == 0

    def get_container_home(self, name: str) -> str | None:
        """Get the HOME environment variable from a container.

        Args:
            name: Container name

        Returns:
            HOME path or None
        """
        format_str = (
            "{{range .Config.Env}}"
            "{{if and (ge (len .) 5) (eq (slice . 0 5) \"HOME=\")}}"
            "{{slice . 5}}"
            "{{end}}"
            "{{end}}"
        )
        result = self.inspect(name, format_=format_str)
        return result if isinstance(result, str) and result else None

    def get_container_path(self, name: str) -> str | None:
        """Get the PATH environment variable from a container.

        Args:
            name: Container name

        Returns:
            PATH value or None
        """
        format_str = (
            "{{range .Config.Env}}"
            "{{if and (ge (len .) 5) (eq (slice . 0 5) \"PATH=\")}}"
            "{{slice . 5}}"
            "{{end}}"
            "{{end}}"
        )
        result = self.inspect(name, format_=format_str)
        return result if isinstance(result, str) and result else None

    def get_unshare_groups(self, name: str) -> bool:
        """Get the unshare_groups label from a container.

        Args:
            name: Container name

        Returns:
            True if unshare_groups is enabled
        """
        format_str = '{{ index .Config.Labels "distrobox.unshare_groups" }}'
        result = self.inspect(name, format_=format_str)
        return result == "1" if isinstance(result, str) else False

    @property
    def is_podman(self) -> bool:
        """Check if this is a podman-based manager."""
        return "podman" in self.name

    @property
    def is_docker(self) -> bool:
        """Check if this is docker."""
        return self.name == "docker"

    def uses_runc(self) -> bool:
        """Check if this manager uses runc runtime.

        Only relevant for podman.
        """
        if not self.is_podman:
            return False

        result = self.run("info")
        return "runc" in result.stdout if result.returncode == 0 else False

    def has_crun(self) -> bool:
        """Check if crun runtime is available."""
        return shutil.which("crun") is not None

    def supports_keepid_size(self, image: str) -> bool:
        """Check if podman supports keep-id:size= option.

        Args:
            image: Image to test with

        Returns:
            True if supported
        """
        if not self.is_podman:
            return False

        result = self.run(
            "run", "--rm", "--userns=keep-id:size=65536",
            image, "/bin/true"
        )
        # Success or command not found (127) means feature is supported
        return result.returncode in (0, 127)


def detect_container_manager(
    preferred: str | None = None,
    verbose: bool = False,
    rootful: bool = False,
    sudo_program: str = "sudo",
) -> ContainerManager:
    """Detect and return an available container manager.

    Detection order: podman -> podman-launcher -> docker -> lilipod

    Args:
        preferred: Preferred container manager name, or "autodetect"
        verbose: Enable verbose logging
        rootful: Use root privileges
        sudo_program: Program to use for root privileges

    Returns:
        ContainerManager instance

    Raises:
        SystemExit: If no container manager is found
    """
    if preferred and preferred != "autodetect":
        if preferred not in SUPPORTED_MANAGERS:
            print(
                f"Invalid container manager: {preferred}",
                file=sys.stderr,
            )
            print(
                f"Available choices: 'autodetect', {', '.join(repr(m) for m in SUPPORTED_MANAGERS)}",
                file=sys.stderr,
            )
            sys.exit(1)

        path = shutil.which(preferred)
        if not path:
            _print_missing_manager_error()
            sys.exit(127)

        return ContainerManager(
            name=preferred,
            path=path,
            verbose=verbose,
            rootful=rootful,
            sudo_program=sudo_program,
        )

    # Autodetect
    for manager in SUPPORTED_MANAGERS:
        path = shutil.which(manager)
        if path:
            return ContainerManager(
                name=manager,
                path=path,
                verbose=verbose,
                rootful=rootful,
                sudo_program=sudo_program,
            )

    _print_missing_manager_error()
    sys.exit(127)


def _print_missing_manager_error() -> None:
    """Print error message for missing container manager."""
    print("Missing dependency: we need a container manager.", file=sys.stderr)
    print("Please install one of podman, docker or lilipod.", file=sys.stderr)
    print("You can follow the documentation on:", file=sys.stderr)
    print("\tman distrobox-compatibility", file=sys.stderr)
    print("or:", file=sys.stderr)
    print(
        "\thttps://github.com/89luca89/distrobox/blob/main/docs/compatibility.md",
        file=sys.stderr,
    )
