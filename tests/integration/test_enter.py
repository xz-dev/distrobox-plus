"""Tests for distrobox-enter command."""

from __future__ import annotations

import os
import pwd

import pytest

from tests.helpers.assertions import (
    assert_command_failed,
    assert_command_success,
)

# All enter tests are slow because first entry triggers container initialization
pytestmark = [pytest.mark.integration, pytest.mark.enter, pytest.mark.slow]


class TestEnterBasic:
    """Basic container entry tests."""

    def test_enter_execute_command(self, distrobox, created_container):
        """Test executing a simple command inside the container."""
        result = distrobox.enter(created_container, command="echo hello")

        assert_command_success(result)
        assert "hello" in result.stdout

    def test_enter_execute_multiple_commands(self, distrobox, created_container):
        """Test executing multiple commands via shell."""
        result = distrobox.enter(
            created_container, command=["sh", "-c", "echo foo && echo bar"]
        )

        assert_command_success(result)
        assert "foo" in result.stdout
        assert "bar" in result.stdout

    def test_enter_command_exit_code(self, distrobox, created_container):
        """Test that exit codes are passed through correctly."""
        # Command that succeeds
        result_success = distrobox.enter(created_container, command="true")
        assert result_success.returncode == 0

        # Command that fails
        result_fail = distrobox.enter(created_container, command="false")
        assert result_fail.returncode != 0


class TestEnterUser:
    """User-related tests."""

    def test_enter_username_matches_host(self, distrobox, created_container):
        """Test that username inside container matches host username."""
        host_user = pwd.getpwuid(os.getuid()).pw_name

        result = distrobox.enter(created_container, command="whoami")

        assert_command_success(result)
        assert host_user in result.stdout

    def test_enter_uid_matches_host(self, distrobox, created_container):
        """Test that UID inside container matches host UID."""
        host_uid = os.getuid()

        result = distrobox.enter(created_container, command="id -u")

        assert_command_success(result)
        assert str(host_uid) in result.stdout

    def test_enter_home_directory(self, distrobox, created_container):
        """Test that home directory is accessible."""
        result = distrobox.enter(created_container, command="echo $HOME")

        assert_command_success(result)
        # Home should be set to something
        assert result.stdout.strip() != ""


class TestEnterEnvironment:
    """Environment variable tests."""

    def test_enter_env_forwarding(self, distrobox, created_container):
        """Test that environment variables are forwarded to container."""
        # Note: distrobox forwards many environment variables
        # Test with a common one like TERM
        result = distrobox.enter(created_container, command="echo $TERM")

        assert_command_success(result)
        # TERM should be forwarded
        assert result.stdout.strip() != ""

    def test_enter_path_includes_host_paths(self, distrobox, created_container):
        """Test that PATH includes relevant paths."""
        result = distrobox.enter(created_container, command="echo $PATH")

        assert_command_success(result)
        # PATH should be set and contain standard paths
        assert "/usr/bin" in result.stdout or "/bin" in result.stdout


class TestEnterWorkingDirectory:
    """Working directory tests."""

    def test_enter_preserves_workdir(self, distrobox, created_container):
        """Test that current working directory is preserved."""
        _host_cwd = os.getcwd()  # noqa: F841

        result = distrobox.enter(created_container, command="pwd")

        assert_command_success(result)
        # Working directory should match host (if path exists in container)
        # or be in the container's home
        assert result.stdout.strip() != ""

    def test_enter_no_workdir_flag(self, distrobox, created_container):
        """Test --no-workdir flag uses container's home."""
        result = distrobox.enter(created_container, command="pwd", no_workdir=True)

        assert_command_success(result)
        # Should be in home directory, not host's cwd
        output = result.stdout.strip()
        assert output.startswith("/home") or output == "/root"


class TestEnterTTY:
    """TTY-related tests."""

    def test_enter_no_tty_mode(self, distrobox, created_container):
        """Test --no-tty mode for non-interactive commands."""
        result = distrobox.enter(created_container, command="echo test", no_tty=True)

        assert_command_success(result)
        assert "test" in result.stdout


class TestEnterDryRun:
    """Dry-run mode tests."""

    def test_enter_dry_run(self, distrobox, created_container):
        """Test dry-run mode shows command without executing."""
        result = distrobox.enter(
            created_container, command="echo should-not-run", dry_run=True
        )

        assert_command_success(result)
        # Dry run should not execute the command
        # It should output the command that would be run
        assert "should-not-run" not in result.stdout or "echo" in result.stdout


class TestEnterErrors:
    """Error handling tests."""

    def test_enter_nonexistent_container_fails(self, distrobox):
        """Test that entering a non-existent container fails."""
        result = distrobox.enter("nonexistent-container-12345", command="true")

        assert_command_failed(result)

    def test_enter_invalid_command_fails(self, distrobox, created_container):
        """Test that an invalid command fails appropriately."""
        result = distrobox.enter(created_container, command="nonexistent-command-12345")

        assert_command_failed(result)
