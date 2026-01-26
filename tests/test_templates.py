"""Tests for utils/templates.py."""

import pytest

from distrobox_boost.utils.templates import (
    generate_additional_packages_cmd,
    generate_hooks_cmd,
    generate_install_cmd,
    generate_upgrade_cmd,
)


class TestGenerateInstallCmd:
    """Tests for generate_install_cmd function."""

    @pytest.fixture
    def sample_packages(self) -> dict[str, list[str]]:
        """Sample package dict for testing."""
        return {
            "apk": ["bash", "curl"],
            "apt": ["bash", "curl"],
            "dnf": ["bash", "curl"],
            "pacman": ["bash", "curl"],
            "zypper": ["bash", "curl"],
        }

    def test_returns_string(self, sample_packages: dict[str, list[str]]) -> None:
        """Should return a string."""
        result = generate_install_cmd(sample_packages)
        assert isinstance(result, str)

    def test_contains_set_e(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain set -e for error handling."""
        result = generate_install_cmd(sample_packages)
        assert "set -e" in result

    def test_contains_apk_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain apk install command with packages."""
        result = generate_install_cmd(sample_packages)
        assert "apk add bash curl" in result

    def test_contains_apt_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain apt-get install command with packages."""
        result = generate_install_cmd(sample_packages)
        assert "apt-get install -y bash curl" in result

    def test_contains_dnf_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain dnf install command with packages."""
        result = generate_install_cmd(sample_packages)
        assert "dnf install -y bash curl" in result

    def test_contains_pacman_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain pacman install command with packages."""
        result = generate_install_cmd(sample_packages)
        assert "pacman -S --noconfirm bash curl" in result

    def test_contains_zypper_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain zypper install command with packages."""
        result = generate_install_cmd(sample_packages)
        assert "zypper install -y bash curl" in result

    def test_contains_fallback_error(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain fallback error for unsupported distributions."""
        result = generate_install_cmd(sample_packages)
        assert "Unsupported distribution" in result
        assert "exit 1" in result

    def test_uses_correct_detection_order(self, sample_packages: dict[str, list[str]]) -> None:
        """Should check package managers in expected order."""
        result = generate_install_cmd(sample_packages)
        apk_pos = result.find("command -v apk")
        apt_pos = result.find("command -v apt-get")
        dnf_pos = result.find("command -v dnf")
        microdnf_pos = result.find("command -v microdnf")
        yum_pos = result.find("command -v yum")
        pacman_pos = result.find("command -v pacman")
        zypper_pos = result.find("command -v zypper")

        assert apk_pos < apt_pos < dnf_pos < microdnf_pos < yum_pos < pacman_pos < zypper_pos


class TestGenerateUpgradeCmd:
    """Tests for generate_upgrade_cmd function."""

    def test_returns_string(self) -> None:
        """Should return a string."""
        result = generate_upgrade_cmd()
        assert isinstance(result, str)

    def test_contains_set_e(self) -> None:
        """Should contain set -e for error handling."""
        result = generate_upgrade_cmd()
        assert "set -e" in result

    def test_contains_apk_upgrade(self) -> None:
        """Should contain apk update and upgrade."""
        result = generate_upgrade_cmd()
        assert "apk update && apk upgrade" in result

    def test_contains_apt_upgrade(self) -> None:
        """Should contain apt-get update and upgrade."""
        result = generate_upgrade_cmd()
        assert "apt-get update" in result
        assert "apt-get upgrade" in result

    def test_contains_dnf_upgrade(self) -> None:
        """Should contain dnf upgrade."""
        result = generate_upgrade_cmd()
        assert "dnf upgrade -y" in result

    def test_contains_pacman_upgrade(self) -> None:
        """Should contain pacman full upgrade."""
        result = generate_upgrade_cmd()
        assert "pacman -Syyu --noconfirm" in result


class TestGenerateHooksCmd:
    """Tests for generate_hooks_cmd function."""

    def test_returns_empty_for_no_hooks(self) -> None:
        """Should return empty string when no hooks provided."""
        result = generate_hooks_cmd([])
        assert result == ""

    def test_returns_single_hook(self) -> None:
        """Should return set -e with single hook command."""
        result = generate_hooks_cmd(["echo hello"])
        assert result == "set -e && echo hello"

    def test_chains_multiple_hooks(self) -> None:
        """Should chain multiple hooks with &&."""
        result = generate_hooks_cmd(["echo hello", "echo world"])
        assert result == "set -e && echo hello && echo world"


class TestGenerateAdditionalPackagesCmd:
    """Tests for generate_additional_packages_cmd function."""

    def test_returns_empty_for_no_packages(self) -> None:
        """Should return empty string when no packages provided."""
        result = generate_additional_packages_cmd([])
        assert result == ""

    def test_contains_set_e(self) -> None:
        """Should contain set -e for error handling."""
        result = generate_additional_packages_cmd(["git"])
        assert "set -e" in result

    def test_contains_package_names(self) -> None:
        """Should contain the package names."""
        result = generate_additional_packages_cmd(["git", "curl", "wget"])
        assert "git curl wget" in result

    def test_contains_all_package_managers(self) -> None:
        """Should contain commands for all package managers."""
        result = generate_additional_packages_cmd(["git"])
        assert "apk add git" in result
        assert "apt-get install -y git" in result
        assert "dnf install -y git" in result
        assert "pacman -S --noconfirm git" in result
        assert "zypper install -y git" in result
