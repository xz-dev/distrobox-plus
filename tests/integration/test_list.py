"""Tests for distrobox-list command."""

from __future__ import annotations

import pytest

from tests.helpers.assertions import (
    assert_command_success,
    assert_container_in_list,
    assert_container_not_in_list,
)

pytestmark = [pytest.mark.integration, pytest.mark.list]


class TestListBasic:
    """Basic list command tests."""

    @pytest.mark.fast
    def test_list_empty(self, distrobox):
        """Test listing when no distrobox containers exist.

        Note: This test may show other distrobox containers if they exist.
        It primarily validates that the list command runs successfully.
        """
        result = distrobox.list()

        assert_command_success(result)

    @pytest.mark.fast
    def test_list_shows_created_container(
        self, distrobox, created_container
    ):
        """Test that a created container appears in the list."""
        result = distrobox.list()

        assert_command_success(result)
        assert_container_in_list(result, created_container)

    @pytest.mark.fast
    def test_list_shows_image_name(
        self, distrobox, created_container
    ):
        """Test that the image name is shown in the list."""
        result = distrobox.list()

        assert_command_success(result)
        # Alpine should appear since we use it as default test image
        assert "alpine" in result.stdout.lower()

    @pytest.mark.fast
    def test_list_shows_status(
        self, distrobox, created_container
    ):
        """Test that container status is shown in the list."""
        result = distrobox.list()

        assert_command_success(result)
        # Status could be "created", "running", "exited", etc.
        # Just verify we get some output
        assert result.stdout.strip() != ""


class TestListFiltering:
    """List filtering tests."""

    @pytest.mark.fast
    def test_list_only_shows_distrobox_containers(
        self, distrobox, created_container, container_manager
    ):
        """Test that only distrobox containers are shown, not all containers.

        Note: This test verifies distrobox containers are shown. It cannot
        easily verify non-distrobox containers are hidden without creating
        a regular container.
        """
        result = distrobox.list()

        assert_command_success(result)
        # Our test container should be visible
        assert_container_in_list(result, created_container)


class TestListMultiple:
    """Multiple container list tests."""

    @pytest.mark.fast
    def test_list_multiple_containers(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test listing multiple distrobox containers."""
        name1 = f"{test_container_name}-1"
        name2 = f"{test_container_name}-2"
        container_cleanup.extend([name1, name2])

        # Create two containers
        result1 = distrobox.create(name1)
        assert_command_success(result1)
        result2 = distrobox.create(name2)
        assert_command_success(result2)

        # List should show both
        list_result = distrobox.list()
        assert_command_success(list_result)
        assert_container_in_list(list_result, name1)
        assert_container_in_list(list_result, name2)
