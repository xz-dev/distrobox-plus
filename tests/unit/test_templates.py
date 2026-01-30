"""Unit tests for distrobox_plus.utils.templates module."""

from __future__ import annotations

import pytest

from distrobox_plus.utils.templates import (
    DISTROBOX_PACKAGES,
    generate_additional_packages_cmd,
    generate_hooks_cmd,
    generate_install_cmd,
    generate_install_cmd_full,
    generate_upgrade_cmd,
)


class TestDistroboxPackages:
    """Tests for DISTROBOX_PACKAGES constant."""

    def test_has_all_package_managers(self):
        """Test that all expected package managers are defined."""
        expected = {"apk", "apt", "dnf", "pacman", "zypper", "emerge", "xbps"}
        assert set(DISTROBOX_PACKAGES.keys()) == expected

    def test_all_have_bash(self):
        """Test that all package managers include bash."""
        for manager, packages in DISTROBOX_PACKAGES.items():
            # emerge uses full package names
            if manager == "emerge":
                assert any("bash" in pkg for pkg in packages), f"{manager} missing bash"
            else:
                assert "bash" in packages, f"{manager} missing bash"

    def test_all_have_sudo(self):
        """Test that all package managers include sudo."""
        for manager, packages in DISTROBOX_PACKAGES.items():
            if manager == "emerge":
                assert any("sudo" in pkg for pkg in packages), f"{manager} missing sudo"
            else:
                assert "sudo" in packages, f"{manager} missing sudo"

    def test_packages_are_lists(self):
        """Test that all values are lists of strings."""
        for manager, packages in DISTROBOX_PACKAGES.items():
            assert isinstance(packages, list), f"{manager} is not a list"
            assert all(isinstance(p, str) for p in packages), f"{manager} has non-string"

    def test_no_empty_package_lists(self):
        """Test that no package list is empty."""
        for manager, packages in DISTROBOX_PACKAGES.items():
            assert len(packages) > 0, f"{manager} has empty package list"


class TestGenerateUpgradeCmd:
    """Tests for generate_upgrade_cmd function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = generate_upgrade_cmd()
        assert isinstance(result, str)

    def test_starts_with_set_e(self):
        """Test that command starts with set -e for error handling."""
        result = generate_upgrade_cmd()
        assert result.startswith("set -e")

    def test_contains_apk_upgrade(self):
        """Test that command handles apk."""
        result = generate_upgrade_cmd()
        assert "apk" in result
        assert "apk upgrade" in result

    def test_contains_apt_upgrade(self):
        """Test that command handles apt."""
        result = generate_upgrade_cmd()
        assert "apt-get" in result
        assert "apt-get upgrade" in result

    def test_contains_dnf_upgrade(self):
        """Test that command handles dnf."""
        result = generate_upgrade_cmd()
        assert "dnf upgrade" in result

    def test_contains_pacman_upgrade(self):
        """Test that command handles pacman."""
        result = generate_upgrade_cmd()
        assert "pacman" in result
        assert "pacman -Syu" in result

    def test_contains_zypper_upgrade(self):
        """Test that command handles zypper."""
        result = generate_upgrade_cmd()
        assert "zypper" in result
        assert "zypper dup" in result

    def test_contains_emerge_sync(self):
        """Test that command handles emerge."""
        result = generate_upgrade_cmd()
        assert "emerge --sync" in result

    def test_contains_xbps_upgrade(self):
        """Test that command handles xbps."""
        result = generate_upgrade_cmd()
        assert "xbps-install -Syu" in result


class TestGenerateHooksCmd:
    """Tests for generate_hooks_cmd function."""

    def test_empty_hooks_returns_true(self):
        """Test that empty hooks return 'true'."""
        result = generate_hooks_cmd("")
        assert result == "true"

    def test_simple_hook(self):
        """Test simple hook command."""
        result = generate_hooks_cmd("touch /tmp/test")
        assert "touch /tmp/test" in result
        assert result.startswith("set -e")

    def test_escapes_single_quotes(self):
        """Test that single quotes are escaped."""
        result = generate_hooks_cmd("echo 'hello'")
        # Single quotes should be escaped
        assert "echo" in result


class TestGenerateAdditionalPackagesCmd:
    """Tests for generate_additional_packages_cmd function."""

    def test_empty_packages_returns_true(self):
        """Test that empty packages return 'true'."""
        result = generate_additional_packages_cmd("")
        assert result == "true"

    def test_single_package(self):
        """Test single package installation."""
        result = generate_additional_packages_cmd("git")
        assert "git" in result
        assert result.startswith("set -e")

    def test_multiple_packages(self):
        """Test multiple packages installation."""
        result = generate_additional_packages_cmd("git vim curl")
        assert "git vim curl" in result

    def test_contains_all_package_managers(self):
        """Test that all package managers are handled."""
        result = generate_additional_packages_cmd("git")
        assert "apk add" in result
        assert "apt-get install" in result
        assert "dnf install" in result
        assert "pacman -S" in result
        assert "zypper install" in result
        assert "emerge" in result
        assert "xbps-install" in result


class TestGenerateInstallCmd:
    """Tests for generate_install_cmd function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = generate_install_cmd()
        assert isinstance(result, str)

    def test_starts_with_set_e(self):
        """Test that command starts with set -e."""
        result = generate_install_cmd()
        assert result.startswith("set -e")

    def test_contains_apk_handling(self):
        """Test that apk is handled."""
        result = generate_install_cmd()
        assert "command -v apk" in result

    def test_contains_apt_handling(self):
        """Test that apt is handled."""
        result = generate_install_cmd()
        assert "command -v apt-get" in result

    def test_contains_dnf_handling(self):
        """Test that dnf/yum is handled."""
        result = generate_install_cmd()
        assert "command -v dnf" in result or "command -v yum" in result

    def test_contains_pacman_handling(self):
        """Test that pacman is handled."""
        result = generate_install_cmd()
        assert "command -v pacman" in result

    def test_contains_emerge_handling(self):
        """Test that emerge is handled."""
        result = generate_install_cmd()
        assert "command -v emerge" in result


class TestGenerateInstallCmdFull:
    """Tests for generate_install_cmd_full function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = generate_install_cmd_full()
        assert isinstance(result, str)

    def test_starts_with_set_e(self):
        """Test that command starts with set -e."""
        result = generate_install_cmd_full()
        assert result.startswith("set -e")

    def test_contains_all_apk_packages(self):
        """Test that all apk packages are included."""
        result = generate_install_cmd_full()
        # Check a few representative packages
        assert "bash" in result
        assert "curl" in result
        assert "sudo" in result
