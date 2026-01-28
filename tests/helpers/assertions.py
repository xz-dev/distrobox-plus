"""Custom assertions for distrobox behavior tests."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.conftest import CommandResult, DistroboxImplementation

__all__ = [
    "assert_command_success",
    "assert_command_failed",
    "assert_container_exists",
    "assert_container_not_exists",
    "assert_container_running",
    "assert_container_stopped",
    "assert_output_contains",
    "assert_output_matches",
    "assert_container_in_list",
    "assert_container_not_in_list",
]


def assert_command_success(result: CommandResult, msg: str | None = None) -> None:
    """Assert that a command succeeded."""
    if not result.success:
        error_msg = msg or f"Command failed: {result.command}"
        error_msg += f"\nReturn code: {result.returncode}"
        error_msg += f"\nStdout: {result.stdout}"
        error_msg += f"\nStderr: {result.stderr}"
        raise AssertionError(error_msg)


def assert_command_failed(
    result: CommandResult, expected_code: int | None = None, msg: str | None = None
) -> None:
    """Assert that a command failed."""
    if result.success:
        error_msg = msg or f"Command unexpectedly succeeded: {result.command}"
        error_msg += f"\nStdout: {result.stdout}"
        error_msg += f"\nStderr: {result.stderr}"
        raise AssertionError(error_msg)

    if expected_code is not None and result.returncode != expected_code:
        raise AssertionError(
            f"Expected return code {expected_code}, got {result.returncode}"
        )


def assert_container_exists(distrobox: DistroboxImplementation, name: str) -> None:
    """Assert that a container exists."""
    if not distrobox.container_exists(name):
        raise AssertionError(f"Container '{name}' does not exist")


def assert_container_not_exists(distrobox: DistroboxImplementation, name: str) -> None:
    """Assert that a container does not exist."""
    if distrobox.container_exists(name):
        raise AssertionError(f"Container '{name}' unexpectedly exists")


def assert_container_running(distrobox: DistroboxImplementation, name: str) -> None:
    """Assert that a container is running."""
    if not distrobox.container_is_running(name):
        raise AssertionError(f"Container '{name}' is not running")


def assert_container_stopped(distrobox: DistroboxImplementation, name: str) -> None:
    """Assert that a container is stopped (exists but not running)."""
    if not distrobox.container_exists(name):
        raise AssertionError(f"Container '{name}' does not exist")
    if distrobox.container_is_running(name):
        raise AssertionError(f"Container '{name}' is still running")


def assert_output_contains(
    result: CommandResult, text: str, *, in_stderr: bool = False
) -> None:
    """Assert that command output contains text."""
    output = result.stderr if in_stderr else result.stdout
    if text not in output:
        source = "stderr" if in_stderr else "stdout"
        raise AssertionError(
            f"Expected '{text}' in {source}, but got:\n{output}"
        )


def assert_output_matches(
    result: CommandResult, pattern: str, *, in_stderr: bool = False
) -> None:
    """Assert that command output matches a regex pattern."""
    output = result.stderr if in_stderr else result.stdout
    if not re.search(pattern, output):
        source = "stderr" if in_stderr else "stdout"
        raise AssertionError(
            f"Expected pattern '{pattern}' to match {source}, but got:\n{output}"
        )


def assert_container_in_list(result: CommandResult, name: str) -> None:
    """Assert that a container appears in distrobox list output."""
    # distrobox list output format varies, but container name should be present
    if name not in result.stdout:
        raise AssertionError(
            f"Container '{name}' not found in list output:\n{result.stdout}"
        )


def assert_container_not_in_list(result: CommandResult, name: str) -> None:
    """Assert that a container does not appear in distrobox list output."""
    if name in result.stdout:
        raise AssertionError(
            f"Container '{name}' unexpectedly found in list output:\n{result.stdout}"
        )
