"""Tests for distrobox-rm command."""

from __future__ import annotations

import pytest

from tests.helpers.assertions import (
    assert_command_failed,
    assert_command_success,
    assert_container_exists,
    assert_container_not_exists,
)

pytestmark = [pytest.mark.integration, pytest.mark.rm]


class TestRmBasic:
    """Basic remove command tests."""

    @pytest.mark.fast
    def test_rm_stopped_container(self, distrobox, created_container, container_cleanup):
        """Test removing a stopped container."""
        # Remove from cleanup list since we're explicitly removing
        container_cleanup.remove(created_container)

        # Verify container exists
        assert_container_exists(distrobox, created_container)

        result = distrobox.rm(created_container)

        assert_command_success(result)
        assert_container_not_exists(distrobox, created_container)

    @pytest.mark.slow  # running_container triggers container initialization
    def test_rm_force_running_container(
        self, distrobox, running_container, container_cleanup
    ):
        """Test force removing a running container."""
        # Remove from cleanup list since we're explicitly removing
        container_cleanup.remove(running_container)

        # Verify container is running
        assert distrobox.container_is_running(running_container)

        result = distrobox.rm(running_container, force=True)

        assert_command_success(result)
        assert_container_not_exists(distrobox, running_container)


class TestRmNonexistent:
    """Non-existent container tests."""

    @pytest.mark.fast
    def test_rm_nonexistent_container(self, distrobox):
        """Test removing a non-existent container.

        Note: distrobox-rm returns 0 even for non-existent containers,
        but prints an error message to stderr.
        """
        result = distrobox.rm("nonexistent-container-12345")

        # distrobox-rm doesn't fail, it just prints a warning
        assert_command_success(result)
        # But it should mention the container wasn't found
        assert "cannot find" in result.stderr.lower() or "no such" in result.stderr.lower()


class TestRmMultiple:
    """Multiple container removal tests."""

    @pytest.mark.fast
    def test_rm_multiple_containers(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test removing multiple containers individually."""
        name1 = f"{test_container_name}-1"
        name2 = f"{test_container_name}-2"
        # Don't add to cleanup since we're removing them

        # Create two containers
        distrobox.create(name1)
        distrobox.create(name2)

        # Remove first
        result1 = distrobox.rm(name1)
        assert_command_success(result1)
        assert_container_not_exists(distrobox, name1)

        # Remove second
        result2 = distrobox.rm(name2)
        assert_command_success(result2)
        assert_container_not_exists(distrobox, name2)


class TestRmAll:
    """Remove all containers tests."""

    @pytest.mark.fast
    def test_rm_all_containers(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test removing all distrobox containers.

        Note: This test only verifies test containers are removed.
        Be careful running this if you have other distrobox containers!
        """
        name1 = f"{test_container_name}-1"
        name2 = f"{test_container_name}-2"
        # Don't add to cleanup since we're removing them

        # Create two containers
        distrobox.create(name1)
        distrobox.create(name2)

        # Verify they exist
        assert_container_exists(distrobox, name1)
        assert_container_exists(distrobox, name2)

        # Remove all - this is destructive!
        # In a real test environment, you might want to skip this
        # or use a more targeted removal
        result = distrobox.rm(all=True, force=True)

        assert_command_success(result)
        # Test containers should be gone
        assert_container_not_exists(distrobox, name1)
        assert_container_not_exists(distrobox, name2)


class TestRmRunningWithoutForce:
    """Tests for removing running containers without force flag."""

    @pytest.mark.slow  # running_container triggers container initialization
    def test_rm_running_without_force_fails(
        self, distrobox, running_container
    ):
        """Test that removing a running container without force fails."""
        result = distrobox.rm(running_container)

        # Should fail without --force
        assert_command_failed(result)
        # Container should still exist
        assert_container_exists(distrobox, running_container)
