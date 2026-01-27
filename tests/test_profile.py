"""Tests for command/profile.py and related utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distrobox_boost.utils.builder import (
    DISTROBOX_PACKAGES,
    build_image,
    generate_containerfile,
)
from distrobox_boost.utils.parsing import (
    BAKED_FIELDS,
    ContainerConfig,
    parse_config_with_header,
    parse_config_without_header,
    parse_multiline_value,
)


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


class TestBuildImage:
    """Tests for build_image function."""

    @patch("distrobox_boost.utils.builder.subprocess.run")
    def test_buildah_uses_bud_command(self, mock_subprocess: MagicMock) -> None:
        """Should use 'bud' subcommand for buildah."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        build_image("buildah", "test-image", "FROM alpine\n")
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "buildah"
        assert call_args[1] == "bud"
        assert "-f" in call_args
        assert "-" in call_args  # Read from stdin

    @patch("distrobox_boost.utils.builder.subprocess.run")
    def test_podman_uses_build_command(self, mock_subprocess: MagicMock) -> None:
        """Should use 'build' subcommand for podman."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        build_image("podman", "test-image", "FROM alpine\n")
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "podman"
        assert call_args[1] == "build"

    @patch("distrobox_boost.utils.builder.subprocess.run")
    def test_docker_uses_build_command(self, mock_subprocess: MagicMock) -> None:
        """Should use 'build' subcommand for docker."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        build_image("docker", "test-image", "FROM alpine\n")
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "docker"
        assert call_args[1] == "build"

    @patch("distrobox_boost.utils.builder.subprocess.run")
    def test_returns_exit_code(self, mock_subprocess: MagicMock) -> None:
        """Should return the subprocess exit code."""
        mock_subprocess.return_value = MagicMock(returncode=42)
        result = build_image("podman", "test-image", "FROM alpine\n")
        assert result == 42

    @patch("distrobox_boost.utils.builder.subprocess.run")
    def test_passes_containerfile_to_stdin(self, mock_subprocess: MagicMock) -> None:
        """Should pass containerfile content to stdin."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        content = "FROM alpine\nRUN echo hello\n"
        build_image("podman", "test-image", content)
        call_kwargs = mock_subprocess.call_args[1]
        assert call_kwargs["input"] == content
        assert call_kwargs["text"] is True


class TestParseMultilineValue:
    """Tests for parse_multiline_value function."""

    def test_empty_string(self) -> None:
        """Should return empty list for empty string."""
        assert parse_multiline_value("") == []

    def test_whitespace_only(self) -> None:
        """Should return empty list for whitespace only."""
        assert parse_multiline_value("   ") == []

    def test_space_separated(self) -> None:
        """Should parse space-separated values."""
        result = parse_multiline_value("git curl wget")
        assert result == ["git", "curl", "wget"]

    def test_quoted_strings(self) -> None:
        """Should parse quoted strings (multiline hooks style)."""
        result = parse_multiline_value('"echo hello" "echo world"')
        assert result == ["echo hello", "echo world"]

    def test_single_quoted_string(self) -> None:
        """Should parse single quoted string."""
        result = parse_multiline_value('"echo hello"')
        assert result == ["echo hello"]


class TestParseConfigWithHeader:
    """Tests for parse_config_with_header function."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Should raise ValueError when file not found."""
        with pytest.raises(ValueError, match="not found"):
            parse_config_with_header(tmp_path / "nonexistent.ini", "test")

    def test_section_not_found(self, tmp_path: Path) -> None:
        """Should raise ValueError when section not found."""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text("[other]\nimage=alpine\n")
        with pytest.raises(ValueError, match="not found"):
            parse_config_with_header(ini_file, "mycontainer")

    def test_parse_basic_config(self, tmp_path: Path) -> None:
        """Should parse basic container config."""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text("""[mycontainer]
image=alpine:latest
additional_packages=git curl
""")
        result = parse_config_with_header(ini_file, "mycontainer")

        assert result.name == "mycontainer"
        assert result.image == "alpine:latest"
        assert result.additional_packages == ["git", "curl"]

    def test_parse_hooks(self, tmp_path: Path) -> None:
        """Should parse hook commands."""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text("""[mycontainer]
image=fedora:latest
pre_init_hooks="echo pre1" "echo pre2"
init_hooks="echo init"
""")
        result = parse_config_with_header(ini_file, "mycontainer")

        assert result.pre_init_hooks == ["echo pre1", "echo pre2"]
        assert result.init_hooks == ["echo init"]

    def test_remaining_options(self, tmp_path: Path) -> None:
        """Should collect non-baked options."""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text("""[mycontainer]
image=alpine:latest
volume=/home:/home
nvidia=true
""")
        result = parse_config_with_header(ini_file, "mycontainer")

        assert "volume" in result.remaining_options
        assert "nvidia" in result.remaining_options
        assert "image" not in result.remaining_options


class TestParseConfigWithoutHeader:
    """Tests for parse_config_without_header function."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Should raise ValueError when file not found."""
        with pytest.raises(ValueError, match="not found"):
            parse_config_without_header(tmp_path / "nonexistent.ini", "test")

    def test_parse_basic_config(self, tmp_path: Path) -> None:
        """Should parse config without section header."""
        ini_file = tmp_path / "config.ini"
        ini_file.write_text("""image=alpine:latest
additional_packages=git curl
""")
        result = parse_config_without_header(ini_file, "mycontainer")

        assert result.name == "mycontainer"
        assert result.image == "alpine:latest"
        assert result.additional_packages == ["git", "curl"]

    def test_parse_hooks(self, tmp_path: Path) -> None:
        """Should parse hook commands."""
        ini_file = tmp_path / "config.ini"
        ini_file.write_text("""image=fedora:latest
pre_init_hooks="echo pre1" "echo pre2"
init_hooks="echo init"
""")
        result = parse_config_without_header(ini_file, "mycontainer")

        assert result.pre_init_hooks == ["echo pre1", "echo pre2"]
        assert result.init_hooks == ["echo init"]

    def test_remaining_options(self, tmp_path: Path) -> None:
        """Should collect non-baked options."""
        ini_file = tmp_path / "config.ini"
        ini_file.write_text("""image=alpine:latest
volume=/home:/home
nvidia=true
""")
        result = parse_config_without_header(ini_file, "mycontainer")

        assert "volume" in result.remaining_options
        assert "nvidia" in result.remaining_options
        assert "image" not in result.remaining_options


class TestGenerateContainerfile:
    """Tests for generate_containerfile function."""

    def test_always_includes_upgrade_and_install(self) -> None:
        """Should always include upgrade and install steps."""
        result = generate_containerfile(
            "alpine:latest",
            upgrade_cmd="apk update && apk upgrade",
            install_cmd="apk add bash",
            pre_init_hooks_cmd="",
            additional_packages_cmd="",
            init_hooks_cmd="",
        )

        assert "FROM alpine:latest" in result
        assert "RUN apk update && apk upgrade" in result
        assert "RUN apk add bash" in result

    def test_includes_pre_hooks_when_present(self) -> None:
        """Should include pre_init_hooks step when command is non-empty."""
        result = generate_containerfile(
            "alpine:latest",
            upgrade_cmd="apk upgrade",
            install_cmd="apk add bash",
            pre_init_hooks_cmd="echo pre-hook",
            additional_packages_cmd="",
            init_hooks_cmd="",
        )

        assert "# Pre-init hooks" in result
        assert "RUN echo pre-hook" in result

    def test_excludes_pre_hooks_when_absent(self) -> None:
        """Should not include pre_init_hooks step when command is empty."""
        result = generate_containerfile(
            "alpine:latest",
            upgrade_cmd="apk upgrade",
            install_cmd="apk add bash",
            pre_init_hooks_cmd="",
            additional_packages_cmd="",
            init_hooks_cmd="",
        )

        assert "Pre-init hooks" not in result

    def test_includes_packages_when_present(self) -> None:
        """Should include additional_packages step when command is non-empty."""
        result = generate_containerfile(
            "alpine:latest",
            upgrade_cmd="apk upgrade",
            install_cmd="apk add bash",
            pre_init_hooks_cmd="",
            additional_packages_cmd="apk add git curl",
            init_hooks_cmd="",
        )

        assert "# Install additional packages" in result
        assert "RUN apk add git curl" in result

    def test_excludes_packages_when_absent(self) -> None:
        """Should not include additional_packages step when command is empty."""
        result = generate_containerfile(
            "alpine:latest",
            upgrade_cmd="apk upgrade",
            install_cmd="apk add bash",
            pre_init_hooks_cmd="",
            additional_packages_cmd="",
            init_hooks_cmd="",
        )

        assert "Install additional packages" not in result

    def test_includes_hooks_when_present(self) -> None:
        """Should include init_hooks step when command is non-empty."""
        result = generate_containerfile(
            "alpine:latest",
            upgrade_cmd="apk upgrade",
            install_cmd="apk add bash",
            pre_init_hooks_cmd="",
            additional_packages_cmd="",
            init_hooks_cmd="echo init-hook",
        )

        assert "# Init hooks" in result
        assert "RUN echo init-hook" in result

    def test_excludes_hooks_when_absent(self) -> None:
        """Should not include init_hooks step when command is empty."""
        result = generate_containerfile(
            "alpine:latest",
            upgrade_cmd="apk upgrade",
            install_cmd="apk add bash",
            pre_init_hooks_cmd="",
            additional_packages_cmd="",
            init_hooks_cmd="",
        )

        assert "Init hooks" not in result

    def test_all_steps_in_correct_order(self) -> None:
        """Should include all steps in correct order when all are present."""
        result = generate_containerfile(
            "alpine:latest",
            upgrade_cmd="apk upgrade",
            install_cmd="apk add bash",
            pre_init_hooks_cmd="echo pre-hook",
            additional_packages_cmd="apk add git",
            init_hooks_cmd="echo init-hook",
        )

        # Check order by finding comment positions
        upgrade_pos = result.find("# Upgrade all packages")
        pre_hooks_pos = result.find("# Pre-init hooks")
        install_pos = result.find("# Install distrobox dependencies")
        packages_pos = result.find("# Install additional packages")
        hooks_pos = result.find("# Init hooks")

        assert upgrade_pos < pre_hooks_pos < install_pos < packages_pos < hooks_pos
