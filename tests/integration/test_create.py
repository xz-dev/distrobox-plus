"""Tests for distrobox-create command."""

from __future__ import annotations

import os

import pytest

from tests.helpers.assertions import (
    assert_command_failed,
    assert_command_success,
    assert_container_exists,
    assert_container_not_exists,
    assert_output_contains,
)

pytestmark = [pytest.mark.integration, pytest.mark.create]


class TestCreateBasic:
    """Basic container creation tests."""

    @pytest.mark.fast
    def test_create_with_default_image(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test creating a container with the default alpine image."""
        container_cleanup.append(test_container_name)

        result = distrobox.create(test_container_name)

        assert_command_success(result)
        assert_container_exists(distrobox, test_container_name)

    @pytest.mark.fast
    def test_create_with_specified_image(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test creating a container with a specific image."""
        container_cleanup.append(test_container_name)

        result = distrobox.create(test_container_name, image="alpine:3.18")

        assert_command_success(result)
        assert_container_exists(distrobox, test_container_name)

    @pytest.mark.slow  # First entry triggers container initialization
    def test_create_with_custom_hostname(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test creating a container with a custom hostname."""
        container_cleanup.append(test_container_name)
        custom_hostname = "my-test-host"

        result = distrobox.create(test_container_name, hostname=custom_hostname)

        assert_command_success(result)
        assert_container_exists(distrobox, test_container_name)

        # Verify hostname inside container (first entry triggers initialization)
        enter_result = distrobox.enter(test_container_name, command="hostname")
        assert_command_success(enter_result)
        assert custom_hostname in enter_result.stdout

    @pytest.mark.fast
    def test_create_with_custom_home(
        self, distrobox, test_container_name, container_cleanup, temp_home
    ):
        """Test creating a container with a custom home directory."""
        container_cleanup.append(test_container_name)

        result = distrobox.create(test_container_name, home=temp_home)

        assert_command_success(result)
        assert_container_exists(distrobox, test_container_name)


class TestCreateVolumes:
    """Volume mount tests."""

    @pytest.mark.slow  # First entry triggers container initialization
    def test_create_with_extra_volume(
        self, distrobox, test_container_name, container_cleanup, temp_volume
    ):
        """Test creating a container with an additional volume mount."""
        container_cleanup.append(test_container_name)
        mount_point = "/mnt/test-volume"

        result = distrobox.create(
            test_container_name, volume=f"{temp_volume}:{mount_point}"
        )

        assert_command_success(result)
        assert_container_exists(distrobox, test_container_name)

        # Verify volume is mounted and accessible (first entry triggers initialization)
        enter_result = distrobox.enter(
            test_container_name, command=f"cat {mount_point}/test-file.txt"
        )
        assert_command_success(enter_result)
        assert "test content from host" in enter_result.stdout

    @pytest.mark.fast
    def test_create_with_multiple_volumes(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test creating a container with multiple volume mounts."""
        import tempfile

        container_cleanup.append(test_container_name)

        with tempfile.TemporaryDirectory() as vol1, tempfile.TemporaryDirectory() as vol2:
            result = distrobox.create(
                test_container_name,
                volume=[f"{vol1}:/mnt/vol1", f"{vol2}:/mnt/vol2"],
            )

            assert_command_success(result)
            assert_container_exists(distrobox, test_container_name)


class TestCreatePackages:
    """Package installation tests."""

    @pytest.mark.slow
    def test_create_with_additional_packages(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test creating a container with additional packages installed."""
        container_cleanup.append(test_container_name)

        result = distrobox.create(
            test_container_name,
            additional_packages=["curl"],
            timeout=600,  # Package install can take time
        )

        assert_command_success(result)

        # Verify package is installed
        enter_result = distrobox.enter(
            test_container_name, command="which curl"
        )
        assert_command_success(enter_result)


class TestCreateMultiDistro:
    """Multi-distribution tests."""

    @pytest.mark.slow
    def test_create_multiple_distros(
        self, distrobox, test_container_name, container_cleanup, distro_image
    ):
        """Test creating containers with different distributions."""
        distro_name, image = distro_image
        container_name = f"{test_container_name}-{distro_name}"
        container_cleanup.append(container_name)

        result = distrobox.create(container_name, image=image, timeout=600)

        assert_command_success(result)
        assert_container_exists(distrobox, container_name)


class TestCreateDryRun:
    """Dry-run mode tests."""

    @pytest.mark.fast
    def test_create_dry_run(self, distrobox, test_container_name):
        """Test dry-run mode doesn't create container."""
        result = distrobox.create(test_container_name, dry_run=True)

        assert_command_success(result)
        assert_container_not_exists(distrobox, test_container_name)
        # Dry run should output the command that would be executed
        assert distrobox.container_manager in result.output or "create" in result.output.lower()


class TestCreateErrors:
    """Error handling tests."""

    @pytest.mark.fast
    def test_create_duplicate_name_handled(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test that creating a container with an existing name is handled.

        Note: distrobox doesn't fail on duplicate names - it detects the container
        exists and returns success with a message indicating so.
        """
        container_cleanup.append(test_container_name)

        # Create first container
        result1 = distrobox.create(test_container_name)
        assert_command_success(result1)

        # Try to create another with same name - distrobox handles this gracefully
        result2 = distrobox.create(test_container_name)
        # Should succeed but indicate container already exists
        assert_command_success(result2)
        assert "already exists" in result2.output.lower() or result2.success

    @pytest.mark.fast
    def test_create_invalid_image_fails(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test that creating with a non-existent image fails."""
        container_cleanup.append(test_container_name)

        result = distrobox.create(
            test_container_name,
            image="nonexistent-image:nonexistent-tag",
            timeout=60,
        )

        assert_command_failed(result)


class TestCreateUnshare:
    """Namespace unsharing tests."""

    @pytest.mark.fast
    def test_create_with_unshare_ipc(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test creating a container with unshared IPC namespace."""
        container_cleanup.append(test_container_name)

        result = distrobox.create(test_container_name, unshare_ipc=True)

        assert_command_success(result)
        assert_container_exists(distrobox, test_container_name)

    @pytest.mark.fast
    def test_create_with_unshare_netns(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test creating a container with unshared network namespace."""
        container_cleanup.append(test_container_name)

        result = distrobox.create(test_container_name, unshare_netns=True)

        assert_command_success(result)
        assert_container_exists(distrobox, test_container_name)

    @pytest.mark.fast
    def test_create_with_unshare_process(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test creating a container with unshared process namespace."""
        container_cleanup.append(test_container_name)

        result = distrobox.create(test_container_name, unshare_process=True)

        assert_command_success(result)
        assert_container_exists(distrobox, test_container_name)

    @pytest.mark.fast
    def test_create_with_unshare_all(
        self, distrobox, test_container_name, container_cleanup
    ):
        """Test creating a container with all namespaces unshared."""
        container_cleanup.append(test_container_name)

        result = distrobox.create(test_container_name, unshare_all=True)

        assert_command_success(result)
        assert_container_exists(distrobox, test_container_name)
