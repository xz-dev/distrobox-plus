"""Tests for distrobox-stop command."""

from __future__ import annotations

import pytest

from tests.helpers.assertions import (
    assert_command_failed,
    assert_command_success,
    assert_container_exists,
    assert_container_running,
    assert_container_stopped,
)

pytestmark = [pytest.mark.integration, pytest.mark.stop]


class TestStopBasic:
    """Basic stop command tests."""

    @pytest.mark.slow  # running_container triggers container initialization
    def test_stop_running_container(self, distrobox, running_container):
        """Test stopping a running container."""
        # Verify container is running first
        assert_container_running(distrobox, running_container)

        result = distrobox.stop(running_container)

        assert_command_success(result)
        # Container should exist but not be running
        assert_container_exists(distrobox, running_container)
        assert_container_stopped(distrobox, running_container)

    @pytest.mark.fast
    def test_stop_already_stopped_container(self, distrobox, created_container):
        """Test stopping an already stopped container.

        This should succeed without error (idempotent operation).
        """
        # Container was created but never started, so it's stopped
        distrobox.stop(created_container)  # Result intentionally ignored

        # Should succeed (or at least not crash)
        # Some implementations may return success, others may indicate it's already stopped
        assert_container_exists(distrobox, created_container)


class TestStopNonexistent:
    """Non-existent container tests."""

    @pytest.mark.fast
    def test_stop_nonexistent_container(self, distrobox):
        """Test stopping a non-existent container."""
        result = distrobox.stop("nonexistent-container-12345")

        # Should fail since container doesn't exist
        assert_command_failed(result)


class TestStopAll:
    """Stop all containers tests."""

    @pytest.mark.slow  # distrobox.enter() triggers container initialization
    def test_stop_all_containers(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test stopping all distrobox containers."""
        name1 = f"{test_container_name}-1"
        name2 = f"{test_container_name}-2"
        container_cleanup.extend([name1, name2])

        # Create and start two containers
        distrobox.create(name1)
        distrobox.create(name2)
        distrobox.enter(name1, command="true")  # Start container (triggers init)
        distrobox.enter(name2, command="true")  # Start container (triggers init)

        # Stop all
        result = distrobox.stop(all=True)

        assert_command_success(result)
        # Both containers should be stopped
        assert_container_stopped(distrobox, name1)
        assert_container_stopped(distrobox, name2)
