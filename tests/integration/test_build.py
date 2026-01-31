"""Tests for distrobox-build command."""

from __future__ import annotations

import subprocess

import pytest

from tests.helpers.assertions import (
    assert_command_failed,
    assert_command_success,
)

pytestmark = [pytest.mark.integration, pytest.mark.build]


class TestBuildHelp:
    """Help and version tests for build command."""

    @pytest.mark.fast
    def test_build_version(self, distrobox):
        """Test build --version output."""
        # Build is python-only command
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.run("build", ["--version"])
        assert_command_success(result)
        assert "distrobox" in result.output.lower()


class TestBuildParser:
    """Parser tests for build command."""

    @pytest.mark.fast
    def test_parser_image_required(self, distrobox):
        """Test that --image is required."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build()
        assert_command_failed(result)

    @pytest.mark.fast
    def test_parser_dry_run_flag(self, distrobox):
        """Test --dry-run flag."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(image="alpine:latest", dry_run=True)
        assert_command_success(result)
        assert "FROM alpine:latest" in result.output

    @pytest.mark.fast
    def test_parser_additional_packages(self, distrobox):
        """Test --additional-packages flag."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(
            image="alpine:latest",
            additional_packages=["git", "vim"],
            dry_run=True,
        )
        assert_command_success(result)
        assert "git vim" in result.output

    @pytest.mark.fast
    def test_parser_init_hooks(self, distrobox):
        """Test --init-hooks flag."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(
            image="alpine:latest",
            init_hooks="touch /tmp/test",
            dry_run=True,
        )
        assert_command_success(result)
        assert "touch /tmp/test" in result.output
        assert "# Init hooks" in result.output

    @pytest.mark.fast
    def test_parser_pre_init_hooks(self, distrobox):
        """Test --pre-init-hooks flag."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(
            image="alpine:latest",
            pre_init_hooks="echo hello",
            dry_run=True,
        )
        assert_command_success(result)
        assert "echo hello" in result.output
        assert "# Pre-init hooks" in result.output


class TestBuildDryRun:
    """Dry-run mode tests."""

    @pytest.mark.fast
    def test_dry_run_shows_containerfile(self, distrobox):
        """Test that dry-run shows the Containerfile."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(image="alpine:latest", dry_run=True)
        assert_command_success(result)
        assert "FROM alpine:latest" in result.output
        assert "/.distrobox-boost" in result.output
        assert "# Upgrade existing packages" in result.output
        assert "# Install distrobox dependencies" in result.output

    @pytest.mark.fast
    def test_dry_run_shows_tag(self, distrobox):
        """Test that dry-run shows the image tag."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(image="alpine:latest", dry_run=True)
        assert_command_success(result)
        assert "Would be tagged as:" in result.output
        assert "-boost:" in result.output

    @pytest.mark.fast
    def test_dry_run_different_packages_different_tags(self, distrobox):
        """Test that different packages produce different tags."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result1 = distrobox.build(
            image="alpine:latest",
            additional_packages=["git"],
            dry_run=True,
        )
        result2 = distrobox.build(
            image="alpine:latest",
            additional_packages=["vim"],
            dry_run=True,
        )
        assert_command_success(result1)
        assert_command_success(result2)

        # Extract tags
        tag1 = [
            line for line in result1.output.split("\n") if "Would be tagged" in line
        ][0]
        tag2 = [
            line for line in result2.output.split("\n") if "Would be tagged" in line
        ][0]
        assert tag1 != tag2


class TestBuildContainerfile:
    """Containerfile generation tests."""

    @pytest.mark.fast
    def test_containerfile_has_boost_marker(self, distrobox):
        """Test that Containerfile creates boost marker."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(image="fedora:latest", dry_run=True)
        assert_command_success(result)
        assert "touch /.distrobox-boost" in result.output

    @pytest.mark.fast
    def test_containerfile_handles_apk(self, distrobox):
        """Test that Containerfile handles apk package manager."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(image="alpine:latest", dry_run=True)
        assert_command_success(result)
        assert "command -v apk" in result.output

    @pytest.mark.fast
    def test_containerfile_handles_apt(self, distrobox):
        """Test that Containerfile handles apt package manager."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(image="ubuntu:22.04", dry_run=True)
        assert_command_success(result)
        assert "command -v apt-get" in result.output

    @pytest.mark.fast
    def test_containerfile_handles_dnf(self, distrobox):
        """Test that Containerfile handles dnf package manager."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(image="fedora:latest", dry_run=True)
        assert_command_success(result)
        assert "command -v dnf" in result.output

    @pytest.mark.fast
    def test_containerfile_handles_pacman(self, distrobox):
        """Test that Containerfile handles pacman package manager."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(image="archlinux:latest", dry_run=True)
        assert_command_success(result)
        assert "command -v pacman" in result.output


class TestBuildActual:
    """Actual build tests (requires container runtime)."""

    @pytest.mark.slow
    def test_build_alpine_image(self, distrobox, container_manager):
        """Test actually building an alpine image."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(
            image="alpine:latest",
            timeout=600,
        )
        assert_command_success(result)
        assert "Successfully built" in result.output or "Built image" in result.output

        # Extract tag from output and verify image exists
        # Clean up the built image
        for line in result.output.split("\n"):
            if "-boost:" in line:
                # Extract tag
                import re

                match = re.search(r"(\S+-boost:\S+)", line)
                if match:
                    tag = match.group(1)
                    subprocess.run([container_manager, "rmi", tag], capture_output=True)
                    break

    @pytest.mark.slow
    def test_build_with_additional_packages(self, distrobox, container_manager):
        """Test building with additional packages."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        result = distrobox.build(
            image="alpine:latest",
            additional_packages=["git"],
            timeout=600,
        )
        assert_command_success(result)

        # Clean up
        for line in result.output.split("\n"):
            if "-boost:" in line:
                import re

                match = re.search(r"(\S+-boost:\S+)", line)
                if match:
                    tag = match.group(1)
                    subprocess.run([container_manager, "rmi", tag], capture_output=True)
                    break

    @pytest.mark.slow
    def test_build_caching(self, distrobox, container_manager):
        """Test that building same config twice uses cache."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        # First build
        result1 = distrobox.build(
            image="alpine:latest",
            additional_packages=["curl"],
            timeout=600,
        )
        assert_command_success(result1)

        # Second build should detect existing image
        result2 = distrobox.build(
            image="alpine:latest",
            additional_packages=["curl"],
            timeout=60,
        )
        assert_command_success(result2)
        # Should indicate using existing image or be much faster

        # Clean up
        for line in result1.output.split("\n"):
            if "-boost:" in line:
                import re

                match = re.search(r"(\S+-boost:\S+)", line)
                if match:
                    tag = match.group(1)
                    subprocess.run([container_manager, "rmi", tag], capture_output=True)
                    break

    @pytest.mark.slow
    def test_build_force_rebuild(self, distrobox, container_manager):
        """Test --force flag rebuilds even when image exists."""
        if distrobox.name == "original":
            pytest.skip("build command is python-only")

        # First build
        result1 = distrobox.build(
            image="alpine:latest",
            timeout=600,
        )
        assert_command_success(result1)

        # Force rebuild
        result2 = distrobox.build(
            image="alpine:latest",
            force=True,
            timeout=600,
        )
        assert_command_success(result2)
        assert "Building boosted image" in result2.output

        # Clean up
        for line in result1.output.split("\n"):
            if "-boost:" in line:
                import re

                match = re.search(r"(\S+-boost:\S+)", line)
                if match:
                    tag = match.group(1)
                    subprocess.run([container_manager, "rmi", tag], capture_output=True)
                    break
