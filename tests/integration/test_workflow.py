"""End-to-end workflow tests for distrobox."""

from __future__ import annotations

import pytest

from tests.helpers.assertions import (
    assert_command_success,
    assert_container_exists,
    assert_container_in_list,
    assert_container_not_exists,
    assert_container_not_in_list,
    assert_container_running,
    assert_container_stopped,
)

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class TestFullLifecycle:
    """Complete container lifecycle tests."""

    def test_full_lifecycle(self, distrobox, test_container_name):
        """Test complete container lifecycle: create -> enter -> stop -> rm."""
        name = test_container_name

        # 1. Create container
        create_result = distrobox.create(name)
        assert_command_success(create_result)
        assert_container_exists(distrobox, name)

        # 2. Verify it appears in list
        list_result = distrobox.list()
        assert_command_success(list_result)
        assert_container_in_list(list_result, name)

        # 3. Enter container and run command
        enter_result = distrobox.enter(name, command="echo 'lifecycle test'")
        assert_command_success(enter_result)
        assert "lifecycle test" in enter_result.stdout

        # 4. Verify container is running after entering
        assert_container_running(distrobox, name)

        # 5. Stop container
        stop_result = distrobox.stop(name)
        assert_command_success(stop_result)
        assert_container_stopped(distrobox, name)

        # 6. Verify still in list but stopped
        list_result2 = distrobox.list()
        assert_command_success(list_result2)
        assert_container_in_list(list_result2, name)

        # 7. Remove container
        rm_result = distrobox.rm(name)
        assert_command_success(rm_result)
        assert_container_not_exists(distrobox, name)

        # 8. Verify no longer in list
        list_result3 = distrobox.list()
        assert_command_success(list_result3)
        assert_container_not_in_list(list_result3, name)

    def test_multiple_entries(self, distrobox, test_container_name, container_cleanup):
        """Test multiple entries into the same container."""
        name = test_container_name
        container_cleanup.append(name)

        # Create container
        distrobox.create(name, check=True)

        # Enter multiple times and verify state is preserved
        distrobox.enter(name, command="touch /tmp/test-file-1", check=True)
        distrobox.enter(name, command="touch /tmp/test-file-2", check=True)

        # Verify both files exist
        result = distrobox.enter(
            name, command="ls /tmp/test-file-1 /tmp/test-file-2"
        )
        assert_command_success(result)
        assert "test-file-1" in result.stdout
        assert "test-file-2" in result.stdout


class TestMultiDistroWorkflow:
    """Multi-distribution workflow tests."""

    def test_multi_distro_workflow(
        self, distrobox, test_container_name, distro_image
    ):
        """Test creating and using containers with different distributions."""
        distro_name, image = distro_image
        name = f"{test_container_name}-{distro_name}"

        # Create container with specific distro
        create_result = distrobox.create(name, image=image, timeout=600)
        assert_command_success(create_result)

        try:
            # Verify we can enter and run a command
            enter_result = distrobox.enter(name, command="cat /etc/os-release")
            assert_command_success(enter_result)

            # Verify it's the right distro (basic check)
            output_lower = enter_result.stdout.lower()
            # Each distro should have its name somewhere in os-release
            if distro_name == "alpine":
                assert "alpine" in output_lower
            elif distro_name == "ubuntu":
                assert "ubuntu" in output_lower
            elif distro_name == "fedora":
                assert "fedora" in output_lower
            elif distro_name == "debian":
                assert "debian" in output_lower
            elif distro_name == "archlinux":
                assert "arch" in output_lower

        finally:
            # Clean up
            distrobox.stop(name)
            distrobox.rm(name, force=True)


class TestRecreateWorkflow:
    """Container recreation workflow tests."""

    def test_recreate_after_removal(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test that a container can be recreated after removal."""
        name = test_container_name
        container_cleanup.append(name)

        # Create first time
        distrobox.create(name, check=True)
        distrobox.enter(name, command="echo first", check=True)

        # Remove
        distrobox.stop(name)
        distrobox.rm(name, force=True, check=True)
        container_cleanup.remove(name)
        assert_container_not_exists(distrobox, name)

        # Recreate
        container_cleanup.append(name)
        distrobox.create(name, check=True)
        assert_container_exists(distrobox, name)

        # Enter again
        result = distrobox.enter(name, command="echo second")
        assert_command_success(result)
        assert "second" in result.stdout


class TestStopAndRestart:
    """Stop and restart workflow tests."""

    def test_stop_and_restart(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test stopping and restarting a container."""
        name = test_container_name
        container_cleanup.append(name)

        # Create and start
        distrobox.create(name, check=True)
        distrobox.enter(name, command="echo started", check=True)
        assert_container_running(distrobox, name)

        # Stop
        distrobox.stop(name, check=True)
        assert_container_stopped(distrobox, name)

        # Start again by entering
        result = distrobox.enter(name, command="echo restarted")
        assert_command_success(result)
        assert "restarted" in result.stdout
        assert_container_running(distrobox, name)
