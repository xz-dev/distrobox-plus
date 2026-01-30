"""Core fixtures and configuration for distrobox behavior tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# Default test image - alpine is fast to pull and start
DEFAULT_TEST_IMAGE = "alpine:latest"

# Container name prefix for test containers
CONTAINER_NAME_PREFIX = "dbx-test"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options."""
    parser.addoption(
        "--implementation",
        action="store",
        default="both",
        choices=["original", "python", "both"],
        help="Which distrobox implementation to test (default: both)",
    )
    parser.addoption(
        "--container-manager",
        action="store",
        default="auto",
        choices=["podman", "docker", "auto"],
        help="Container manager to use (default: auto-detect)",
    )
    parser.addoption(
        "--keep-containers",
        action="store_true",
        default=False,
        help="Keep test containers after tests complete (for debugging)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    # Markers are defined in pyproject.toml, but we can add runtime config here
    pass


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Modify test collection based on command line options."""
    implementation = config.getoption("--implementation")

    if implementation == "both":
        return

    # Filter tests to only run for the specified implementation
    for item in items:
        if "implementation" in item.fixturenames:
            # The fixture will handle filtering
            pass


@dataclass
class CommandResult:
    """Result of running a distrobox command."""

    returncode: int
    stdout: str
    stderr: str
    command: list[str]

    @property
    def success(self) -> bool:
        """Return True if command succeeded."""
        return self.returncode == 0

    @property
    def output(self) -> str:
        """Return combined stdout and stderr."""
        return self.stdout + self.stderr


@dataclass
class DistroboxImplementation:
    """Abstraction for running distrobox commands with different implementations."""

    name: str  # "original" or "python"
    container_manager: str  # "podman" or "docker"
    _env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set up environment for the implementation."""
        self._env = os.environ.copy()
        self._env["DBX_CONTAINER_MANAGER"] = self.container_manager

    def _get_command_prefix(self, command: str) -> list[str]:
        """Get the command prefix for the implementation."""
        if self.name == "original":
            # Use system distrobox commands
            return [f"distrobox-{command}"]
        else:
            # Use Python implementation
            return ["distrobox-plus", command]

    def run(
        self,
        command: str,
        args: list[str] | None = None,
        *,
        check: bool = False,
        timeout: int = 300,
        input_text: str | None = None,
    ) -> CommandResult:
        """Run a distrobox command.

        Args:
            command: The distrobox subcommand (create, enter, list, stop, rm)
            args: Additional arguments to pass
            check: If True, raise on non-zero exit code
            timeout: Command timeout in seconds
            input_text: Optional input to send to stdin

        Returns:
            CommandResult with returncode, stdout, stderr
        """
        cmd = self._get_command_prefix(command)
        if args:
            cmd.extend(args)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self._env,
            timeout=timeout,
            input=input_text,
        )

        cmd_result = CommandResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            command=cmd,
        )

        if check and not cmd_result.success:
            raise subprocess.CalledProcessError(
                result.returncode,
                cmd,
                result.stdout,
                result.stderr,
            )

        return cmd_result

    def create(self, name: str, **kwargs) -> CommandResult:
        """Create a distrobox container."""
        args = ["--name", name]

        if "image" in kwargs:
            args.extend(["--image", kwargs["image"]])
        else:
            args.extend(["--image", DEFAULT_TEST_IMAGE])

        if kwargs.get("yes", True):
            args.append("--yes")

        if "hostname" in kwargs:
            args.extend(["--hostname", kwargs["hostname"]])

        if "home" in kwargs:
            args.extend(["--home", kwargs["home"]])

        if "volume" in kwargs:
            for vol in (
                kwargs["volume"]
                if isinstance(kwargs["volume"], list)
                else [kwargs["volume"]]
            ):
                args.extend(["--volume", vol])

        if "additional_packages" in kwargs:
            for pkg in kwargs["additional_packages"]:
                args.extend(["--additional-packages", pkg])

        if kwargs.get("dry_run"):
            args.append("--dry-run")

        if kwargs.get("unshare_ipc"):
            args.append("--unshare-ipc")

        if kwargs.get("unshare_netns"):
            args.append("--unshare-netns")

        if kwargs.get("unshare_process"):
            args.append("--unshare-process")

        if kwargs.get("unshare_devsys"):
            args.append("--unshare-devsys")

        if kwargs.get("unshare_all"):
            args.append("--unshare-all")

        return self.run(
            "create",
            args,
            **{k: v for k, v in kwargs.items() if k in ("check", "timeout")},
        )

    def enter(self, name: str, **kwargs) -> CommandResult:
        """Enter a distrobox container.

        Note: First entry into a container triggers initialization which can
        take several minutes (installing packages, creating user, etc.).
        The default timeout is set to 600 seconds to accommodate this.
        """
        args = ["--name", name]

        if "command" in kwargs:
            args.append("--")
            cmd = kwargs["command"]
            if isinstance(cmd, list):
                args.extend(cmd)
            else:
                args.append(cmd)

        if kwargs.get("no_workdir"):
            args.insert(0, "--no-workdir")

        if kwargs.get("no_tty"):
            args.insert(0, "--no-tty")

        if kwargs.get("dry_run"):
            args.insert(0, "--dry-run")

        # Default timeout for enter is longer due to first-run initialization
        run_kwargs = {k: v for k, v in kwargs.items() if k in ("check", "input_text")}
        run_kwargs["timeout"] = kwargs.get("timeout", 600)

        return self.run("enter", args, **run_kwargs)

    def list(self, **kwargs) -> CommandResult:
        """List distrobox containers."""
        args = []

        if kwargs.get("no_color"):
            args.append("--no-color")

        return self.run(
            "list",
            args,
            **{k: v for k, v in kwargs.items() if k in ("check", "timeout")},
        )

    def stop(self, name: str | None = None, **kwargs) -> CommandResult:
        """Stop distrobox container(s).

        Note: distrobox-stop takes container name as positional argument, not --name.
        """
        args = []

        if kwargs.get("all"):
            args.append("--all")

        if kwargs.get("yes", True):
            args.append("--yes")

        # Container name is positional, not --name
        if name:
            args.append(name)

        return self.run(
            "stop",
            args,
            **{k: v for k, v in kwargs.items() if k in ("check", "timeout")},
        )

    def rm(self, name: str | None = None, **kwargs) -> CommandResult:
        """Remove distrobox container(s).

        Note: distrobox-rm takes container name as positional argument, not --name.
        """
        args = []

        if kwargs.get("all"):
            args.append("--all")

        if kwargs.get("force"):
            args.append("--force")

        if kwargs.get("yes", True):
            args.append("--yes")

        # Container name is positional, not --name
        if name:
            args.append(name)

        return self.run(
            "rm", args, **{k: v for k, v in kwargs.items() if k in ("check", "timeout")}
        )

    def container_exists(self, name: str) -> bool:
        """Check if a container exists."""
        result = subprocess.run(
            [self.container_manager, "container", "exists", name],
            capture_output=True,
        )
        return result.returncode == 0

    def container_is_running(self, name: str) -> bool:
        """Check if a container is running."""
        result = subprocess.run(
            [self.container_manager, "inspect", "--format", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def force_remove_container(self, name: str) -> None:
        """Force remove a container using the container manager directly."""
        subprocess.run(
            [self.container_manager, "rm", "-f", name],
            capture_output=True,
        )


def _detect_container_manager() -> str:
    """Detect available container manager."""
    if shutil.which("podman"):
        return "podman"
    elif shutil.which("docker"):
        return "docker"
    else:
        raise RuntimeError("No container manager found (podman or docker)")


@pytest.fixture(scope="session")
def container_manager(request: pytest.FixtureRequest) -> str:
    """Get the container manager to use for tests."""
    manager = request.config.getoption("--container-manager")
    if manager == "auto":
        return _detect_container_manager()
    return manager


@pytest.fixture(scope="session")
def keep_containers(request: pytest.FixtureRequest) -> bool:
    """Whether to keep containers after tests."""
    return request.config.getoption("--keep-containers")


def _get_implementations(
    request: pytest.FixtureRequest, container_manager: str
) -> list[str]:
    """Get list of implementations to test based on command line option."""
    impl_option = request.config.getoption("--implementation")
    if impl_option == "both":
        return ["original", "python"]
    return [impl_option]


@pytest.fixture(params=["original", "python"])
def implementation(
    request: pytest.FixtureRequest, container_manager: str
) -> DistroboxImplementation:
    """Parameterized fixture that provides both implementations."""
    impl_option = request.config.getoption("--implementation")

    # Skip if this implementation is not selected
    if impl_option != "both" and request.param != impl_option:
        pytest.skip(f"Skipping {request.param} (--implementation={impl_option})")

    return DistroboxImplementation(
        name=request.param, container_manager=container_manager
    )


@pytest.fixture
def distrobox(implementation: DistroboxImplementation) -> DistroboxImplementation:
    """Alias for implementation fixture for cleaner test code."""
    return implementation


@pytest.fixture
def test_container_name() -> str:
    """Generate a unique container name for testing."""
    return f"{CONTAINER_NAME_PREFIX}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def container_cleanup(
    distrobox: DistroboxImplementation, keep_containers: bool
) -> Generator[list[str], None, None]:
    """Fixture that tracks and cleans up containers after tests.

    Usage:
        def test_something(distrobox, container_cleanup):
            name = "my-test-container"
            container_cleanup.append(name)
            distrobox.create(name)
            # container will be cleaned up after test
    """
    containers: list[str] = []
    yield containers

    if keep_containers:
        if containers:
            print(f"\nKeeping containers for debugging: {containers}")
        return

    # Clean up containers in reverse order
    for name in reversed(containers):
        try:
            distrobox.force_remove_container(name)
        except Exception as e:
            print(f"Warning: Failed to clean up container {name}: {e}")


@pytest.fixture
def created_container(
    distrobox: DistroboxImplementation,
    test_container_name: str,
    container_cleanup: list[str],
) -> Generator[str, None, None]:
    """Create a container and register it for cleanup.

    Returns the container name.
    """
    container_cleanup.append(test_container_name)
    result = distrobox.create(test_container_name)
    assert result.success, f"Failed to create container: {result.stderr}"
    yield test_container_name


@pytest.fixture
def initialized_container(
    distrobox: DistroboxImplementation,
    created_container: str,
) -> Generator[str, None, None]:
    """Create and initialize a container (first entry to trigger setup).

    This fixture handles the slow first-entry initialization that distrobox
    performs (creating user, installing packages, etc.).

    Returns the container name.
    """
    # First entry triggers initialization - this can take several minutes
    result = distrobox.enter(created_container, command="true", timeout=600)
    assert result.success, f"Failed to initialize container: {result.stderr}"
    yield created_container


@pytest.fixture
def running_container(
    distrobox: DistroboxImplementation,
    initialized_container: str,
) -> Generator[str, None, None]:
    """Provide a running, initialized container.

    Returns the container name.
    """
    # Container should already be running after initialization
    yield initialized_container
