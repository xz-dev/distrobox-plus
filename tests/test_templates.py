"""Tests for utils/templates.py."""

import pytest

from distrobox_boost.utils.templates import generate_install_script


class TestGenerateInstallScript:
    """Tests for generate_install_script function."""

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
        result = generate_install_script(sample_packages)
        assert isinstance(result, str)

    def test_starts_with_shebang(self, sample_packages: dict[str, list[str]]) -> None:
        """Should start with shell shebang."""
        result = generate_install_script(sample_packages)
        assert result.startswith("#!/bin/sh")

    def test_contains_set_e(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain set -e for error handling."""
        result = generate_install_script(sample_packages)
        assert "set -e" in result

    def test_contains_apk_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain apk install command with packages (no update, assumes upgrade already ran)."""
        result = generate_install_script(sample_packages)
        assert "apk add bash curl" in result

    def test_contains_apt_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain apt-get install command with packages (no update, assumes upgrade already ran)."""
        result = generate_install_script(sample_packages)
        assert "apt-get install -y bash curl" in result

    def test_contains_dnf_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain dnf install command with packages."""
        result = generate_install_script(sample_packages)
        assert "dnf install -y bash curl" in result

    def test_contains_pacman_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain pacman install command with packages (no -u, assumes upgrade already ran)."""
        result = generate_install_script(sample_packages)
        assert "pacman -S --noconfirm bash curl" in result

    def test_contains_zypper_command(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain zypper install command with packages."""
        result = generate_install_script(sample_packages)
        assert "zypper install -y bash curl" in result

    def test_contains_fallback_error(self, sample_packages: dict[str, list[str]]) -> None:
        """Should contain fallback error for unsupported distributions."""
        result = generate_install_script(sample_packages)
        assert "Unsupported distribution" in result
        assert "exit 1" in result

    def test_uses_correct_detection_order(self, sample_packages: dict[str, list[str]]) -> None:
        """Should check package managers in expected order."""
        result = generate_install_script(sample_packages)
        apk_pos = result.find("command -v apk")
        apt_pos = result.find("command -v apt-get")
        dnf_pos = result.find("command -v dnf")
        microdnf_pos = result.find("command -v microdnf")
        yum_pos = result.find("command -v yum")
        pacman_pos = result.find("command -v pacman")
        zypper_pos = result.find("command -v zypper")

        assert apk_pos < apt_pos < dnf_pos < microdnf_pos < yum_pos < pacman_pos < zypper_pos
