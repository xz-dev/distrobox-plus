"""Tests for command/image.py."""

from unittest.mock import MagicMock, patch

import pytest

from distrobox_boost.command.image import (
    DISTROBOX_PACKAGES,
    build_image,
    generate_containerfile,
    run,
)
from distrobox_boost.utils.utils import get_image_builder


class TestDistroboxPackages:
    """Tests for DISTROBOX_PACKAGES constant."""

    def test_has_all_package_managers(self) -> None:
        """Should have entries for all supported package managers."""
        expected_managers = {"apk", "apt", "dnf", "pacman", "zypper"}
        assert set(DISTROBOX_PACKAGES.keys()) == expected_managers

    def test_all_managers_have_bash(self) -> None:
        """All package managers should include bash."""
        for manager, packages in DISTROBOX_PACKAGES.items():
            assert "bash" in packages, f"{manager} should include bash"

    def test_all_managers_have_sudo(self) -> None:
        """All package managers should include sudo."""
        for manager, packages in DISTROBOX_PACKAGES.items():
            assert "sudo" in packages, f"{manager} should include sudo"

    def test_all_managers_have_curl(self) -> None:
        """All package managers should include curl."""
        for manager, packages in DISTROBOX_PACKAGES.items():
            assert "curl" in packages, f"{manager} should include curl"

    def test_packages_are_non_empty(self) -> None:
        """All package lists should be non-empty."""
        for manager, packages in DISTROBOX_PACKAGES.items():
            assert len(packages) > 0, f"{manager} should have packages"


class TestGetImageBuilder:
    """Tests for get_image_builder function."""

    @patch("distrobox_boost.utils.utils.shutil.which")
    def test_returns_buildah_when_available(self, mock_which: MagicMock) -> None:
        """Should return 'buildah' when buildah is available."""
        mock_which.side_effect = lambda cmd: "/usr/bin/buildah" if cmd == "buildah" else None
        assert get_image_builder() == "buildah"

    @patch("distrobox_boost.utils.utils.shutil.which")
    def test_returns_podman_when_buildah_unavailable(self, mock_which: MagicMock) -> None:
        """Should return 'podman' when only podman is available."""
        mock_which.side_effect = lambda cmd: "/usr/bin/podman" if cmd == "podman" else None
        assert get_image_builder() == "podman"

    @patch("distrobox_boost.utils.utils.shutil.which")
    def test_returns_docker_when_others_unavailable(self, mock_which: MagicMock) -> None:
        """Should return 'docker' when only docker is available."""
        mock_which.side_effect = lambda cmd: "/usr/bin/docker" if cmd == "docker" else None
        assert get_image_builder() == "docker"

    @patch("distrobox_boost.utils.utils.shutil.which")
    def test_returns_none_when_no_builder(self, mock_which: MagicMock) -> None:
        """Should return None when no builder is available."""
        mock_which.return_value = None
        assert get_image_builder() is None

    @patch("distrobox_boost.utils.utils.shutil.which")
    def test_prefers_buildah_over_podman_and_docker(self, mock_which: MagicMock) -> None:
        """Should prefer buildah when all builders are available."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        assert get_image_builder() == "buildah"

    @patch("distrobox_boost.utils.utils.shutil.which")
    def test_prefers_podman_over_docker(self, mock_which: MagicMock) -> None:
        """Should prefer podman over docker when buildah unavailable."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}" if cmd in ("podman", "docker") else None
        assert get_image_builder() == "podman"


class TestBuildImage:
    """Tests for build_image function."""

    @patch("subprocess.run")
    def test_buildah_uses_bud_command(self, mock_subprocess: MagicMock) -> None:
        """Should use 'bud' subcommand for buildah."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        build_image("buildah", "test-image", "/tmp/Containerfile", "/tmp")
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "buildah"
        assert call_args[1] == "bud"

    @patch("subprocess.run")
    def test_podman_uses_build_command(self, mock_subprocess: MagicMock) -> None:
        """Should use 'build' subcommand for podman."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        build_image("podman", "test-image", "/tmp/Containerfile", "/tmp")
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "podman"
        assert call_args[1] == "build"

    @patch("subprocess.run")
    def test_docker_uses_build_command(self, mock_subprocess: MagicMock) -> None:
        """Should use 'build' subcommand for docker."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        build_image("docker", "test-image", "/tmp/Containerfile", "/tmp")
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "docker"
        assert call_args[1] == "build"

    @patch("subprocess.run")
    def test_returns_exit_code(self, mock_subprocess: MagicMock) -> None:
        """Should return the subprocess exit code."""
        mock_subprocess.return_value = MagicMock(returncode=42)
        result = build_image("podman", "test-image", "/tmp/Containerfile", "/tmp")
        assert result == 42


class TestGenerateContainerfile:
    """Tests for generate_containerfile function."""

    def test_returns_string(self) -> None:
        """Should return a string."""
        result = generate_containerfile("fedora:latest")
        assert isinstance(result, str)

    def test_contains_from_directive(self) -> None:
        """Should contain FROM with base image."""
        result = generate_containerfile("fedora:latest")
        assert "FROM fedora:latest" in result

    def test_copies_upgrade_script(self) -> None:
        """Should copy upgrade.sh to container."""
        result = generate_containerfile("fedora:latest")
        assert "COPY upgrade.sh /tmp/upgrade.sh" in result

    def test_runs_upgrade_script(self) -> None:
        """Should run upgrade.sh in RUN directive."""
        result = generate_containerfile("fedora:latest")
        assert "chmod +x /tmp/upgrade.sh" in result
        assert "/tmp/upgrade.sh" in result

    def test_cleans_up_upgrade_script(self) -> None:
        """Should remove upgrade.sh after running."""
        result = generate_containerfile("fedora:latest")
        assert "rm /tmp/upgrade.sh" in result

    def test_copies_install_script(self) -> None:
        """Should copy install.sh to container."""
        result = generate_containerfile("fedora:latest")
        assert "COPY install.sh /tmp/install.sh" in result

    def test_runs_install_script(self) -> None:
        """Should run install.sh in RUN directive."""
        result = generate_containerfile("fedora:latest")
        assert "chmod +x /tmp/install.sh" in result
        assert "/tmp/install.sh" in result

    def test_cleans_up_install_script(self) -> None:
        """Should remove install.sh after running."""
        result = generate_containerfile("fedora:latest")
        assert "rm /tmp/install.sh" in result

    def test_uses_provided_base_image(self) -> None:
        """Should use the provided base image."""
        result = generate_containerfile("docker.io/library/ubuntu:22.04")
        assert "FROM docker.io/library/ubuntu:22.04" in result

    def test_upgrade_runs_before_install(self) -> None:
        """Should run upgrade script before install script."""
        result = generate_containerfile("fedora:latest")
        upgrade_pos = result.find("upgrade.sh")
        install_pos = result.find("install.sh")
        assert upgrade_pos < install_pos, "upgrade.sh should come before install.sh"


class TestRun:
    """Tests for run function."""

    @patch("distrobox_boost.command.image.get_image_builder")
    def test_returns_error_when_no_builder(self, mock_builder: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
        """Should return 1 when no image builder is found."""
        mock_builder.return_value = None
        result = run("test-image", "fedora:latest")
        assert result == 1
        captured = capsys.readouterr()
        assert "No image builder found" in captured.out

    @patch("subprocess.run")
    @patch("distrobox_boost.command.image.get_image_builder")
    def test_calls_build_command(self, mock_builder: MagicMock, mock_subprocess: MagicMock) -> None:
        """Should call image builder build command."""
        mock_builder.return_value = "podman"
        mock_subprocess.return_value = MagicMock(returncode=0)

        run("test-image", "fedora:latest")

        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "podman"
        assert call_args[1] == "build"
        assert "-t" in call_args
        assert "test-image" in call_args

    @patch("subprocess.run")
    @patch("distrobox_boost.command.image.get_image_builder")
    def test_returns_build_exit_code(self, mock_builder: MagicMock, mock_subprocess: MagicMock) -> None:
        """Should return the build command exit code."""
        mock_builder.return_value = "podman"
        mock_subprocess.return_value = MagicMock(returncode=42)

        result = run("test-image", "fedora:latest")
        assert result == 42

    @patch("subprocess.run")
    @patch("distrobox_boost.command.image.get_image_builder")
    def test_success_message_on_success(
        self, mock_builder: MagicMock, mock_subprocess: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should print success message when build succeeds."""
        mock_builder.return_value = "podman"
        mock_subprocess.return_value = MagicMock(returncode=0)

        run("test-image", "fedora:latest")

        captured = capsys.readouterr()
        assert "Successfully built image: test-image" in captured.out

    @patch("subprocess.run")
    @patch("distrobox_boost.command.image.get_image_builder")
    def test_failure_message_on_failure(
        self, mock_builder: MagicMock, mock_subprocess: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should print failure message when build fails."""
        mock_builder.return_value = "podman"
        mock_subprocess.return_value = MagicMock(returncode=1)

        run("test-image", "fedora:latest")

        captured = capsys.readouterr()
        assert "Failed to build image: test-image" in captured.out
