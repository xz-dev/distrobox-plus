"""Unit tests for distrobox_plus.utils.builder module."""

from __future__ import annotations

import pytest

from distrobox_plus.utils.builder import (
    generate_containerfile,
    get_boost_image_name,
    get_boost_image_tag,
)


class TestGetBoostImageName:
    """Tests for get_boost_image_name function."""

    def test_simple_name(self):
        """Test simple image name."""
        result = get_boost_image_name("alpine")
        assert result == "alpine:distrobox-plus"

    def test_name_with_tag(self):
        """Test image name with tag."""
        result = get_boost_image_name("alpine:latest")
        assert result == "alpine-latest:distrobox-plus"

    def test_name_with_registry(self):
        """Test image name with registry."""
        result = get_boost_image_name("docker.io/library/alpine")
        assert result == "docker.io-library-alpine:distrobox-plus"

    def test_uppercase_converted(self):
        """Test that uppercase is converted to lowercase."""
        result = get_boost_image_name("Ubuntu:22.04")
        assert result == "ubuntu-22.04:distrobox-plus"


class TestGetBoostImageTag:
    """Tests for get_boost_image_tag function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = get_boost_image_tag("alpine:latest")
        assert isinstance(result, str)

    def test_contains_boost(self):
        """Test that tag contains 'boost'."""
        result = get_boost_image_tag("alpine:latest")
        assert "-boost:" in result

    def test_same_inputs_same_hash(self):
        """Test that same inputs produce same hash."""
        result1 = get_boost_image_tag("alpine:latest", "git", "hook1", "hook2")
        result2 = get_boost_image_tag("alpine:latest", "git", "hook1", "hook2")
        assert result1 == result2

    def test_different_image_different_hash(self):
        """Test that different images produce different hashes."""
        result1 = get_boost_image_tag("alpine:latest")
        result2 = get_boost_image_tag("fedora:latest")
        assert result1 != result2

    def test_different_packages_different_hash(self):
        """Test that different packages produce different hashes."""
        result1 = get_boost_image_tag("alpine:latest", "git")
        result2 = get_boost_image_tag("alpine:latest", "vim")
        assert result1 != result2

    def test_different_hooks_different_hash(self):
        """Test that different hooks produce different hashes."""
        result1 = get_boost_image_tag("alpine:latest", "", "hook1")
        result2 = get_boost_image_tag("alpine:latest", "", "hook2")
        assert result1 != result2

    def test_hash_length(self):
        """Test that hash is 12 characters."""
        result = get_boost_image_tag("alpine:latest")
        # Format: name-boost:hash
        hash_part = result.split(":")[-1]
        assert len(hash_part) == 12


class TestGenerateContainerfile:
    """Tests for generate_containerfile function."""

    def test_starts_with_from(self):
        """Test that Containerfile starts with FROM."""
        result = generate_containerfile("alpine:latest")
        assert result.startswith("FROM alpine:latest")

    def test_contains_boost_marker(self):
        """Test that Containerfile creates boost marker."""
        result = generate_containerfile("alpine:latest")
        assert "touch /.distrobox-boost" in result

    def test_contains_upgrade(self):
        """Test that Containerfile upgrades packages."""
        result = generate_containerfile("alpine:latest")
        assert "# Upgrade existing packages" in result
        assert "RUN set -e" in result

    def test_contains_install(self):
        """Test that Containerfile installs dependencies."""
        result = generate_containerfile("alpine:latest")
        assert "# Install distrobox dependencies" in result

    def test_no_additional_packages_without_arg(self):
        """Test that additional packages section is absent without arg."""
        result = generate_containerfile("alpine:latest")
        assert "# Install additional packages" not in result

    def test_has_additional_packages_with_arg(self):
        """Test that additional packages section is present with arg."""
        result = generate_containerfile("alpine:latest", additional_packages="git vim")
        assert "# Install additional packages" in result
        assert "git vim" in result

    def test_no_init_hooks_without_arg(self):
        """Test that init hooks section is absent without arg."""
        result = generate_containerfile("alpine:latest")
        assert "# Init hooks" not in result

    def test_has_init_hooks_with_arg(self):
        """Test that init hooks section is present with arg."""
        result = generate_containerfile("alpine:latest", init_hooks="touch /tmp/test")
        assert "# Init hooks" in result
        assert "touch /tmp/test" in result

    def test_no_pre_init_hooks_without_arg(self):
        """Test that pre-init hooks section is absent without arg."""
        result = generate_containerfile("alpine:latest")
        assert "# Pre-init hooks" not in result

    def test_has_pre_init_hooks_with_arg(self):
        """Test that pre-init hooks section is present with arg."""
        result = generate_containerfile("alpine:latest", pre_init_hooks="echo hello")
        assert "# Pre-init hooks" in result
        assert "echo hello" in result

    def test_order_of_sections(self):
        """Test that sections appear in correct order."""
        result = generate_containerfile(
            "alpine:latest",
            additional_packages="git",
            init_hooks="hook1",
            pre_init_hooks="hook0",
        )
        lines = result.split("\n")

        # Find positions
        boost_pos = None
        upgrade_pos = None
        pre_hook_pos = None
        install_pos = None
        additional_pos = None
        init_hook_pos = None

        for i, line in enumerate(lines):
            if "/.distrobox-boost" in line:
                boost_pos = i
            if "# Upgrade" in line:
                upgrade_pos = i
            if "# Pre-init hooks" in line:
                pre_hook_pos = i
            if "# Install distrobox dependencies" in line:
                install_pos = i
            if "# Install additional packages" in line:
                additional_pos = i
            if "# Init hooks" in line:
                init_hook_pos = i

        # Verify order
        assert boost_pos is not None
        assert upgrade_pos is not None
        assert pre_hook_pos is not None
        assert install_pos is not None
        assert additional_pos is not None
        assert init_hook_pos is not None

        assert boost_pos < upgrade_pos
        assert upgrade_pos < pre_hook_pos
        assert pre_hook_pos < install_pos
        assert install_pos < additional_pos
        assert additional_pos < init_hook_pos

    def test_returns_multiline_string(self):
        """Test that result is a valid multiline Containerfile."""
        result = generate_containerfile("alpine:latest")
        lines = result.split("\n")
        assert len(lines) > 5  # Should have multiple lines
        assert lines[0].startswith("FROM")
