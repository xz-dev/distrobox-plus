"""Tests for command/assemble.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distrobox_boost.command.assemble import (
    DISTROBOX_PACKAGES,
    ContainerConfig,
    _parse_multiline_value,
    build_image,
    generate_assemble_content,
    generate_containerfile,
    parse_assemble_file,
    run_assemble,
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

    @patch("distrobox_boost.command.assemble.subprocess.run")
    def test_buildah_uses_bud_command(self, mock_subprocess: MagicMock) -> None:
        """Should use 'bud' subcommand for buildah."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        build_image("buildah", "test-image", "/tmp/Containerfile", "/tmp")
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "buildah"
        assert call_args[1] == "bud"

    @patch("distrobox_boost.command.assemble.subprocess.run")
    def test_podman_uses_build_command(self, mock_subprocess: MagicMock) -> None:
        """Should use 'build' subcommand for podman."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        build_image("podman", "test-image", "/tmp/Containerfile", "/tmp")
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "podman"
        assert call_args[1] == "build"

    @patch("distrobox_boost.command.assemble.subprocess.run")
    def test_docker_uses_build_command(self, mock_subprocess: MagicMock) -> None:
        """Should use 'build' subcommand for docker."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        build_image("docker", "test-image", "/tmp/Containerfile", "/tmp")
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "docker"
        assert call_args[1] == "build"

    @patch("distrobox_boost.command.assemble.subprocess.run")
    def test_returns_exit_code(self, mock_subprocess: MagicMock) -> None:
        """Should return the subprocess exit code."""
        mock_subprocess.return_value = MagicMock(returncode=42)
        result = build_image("podman", "test-image", "/tmp/Containerfile", "/tmp")
        assert result == 42


class TestParseMultilineValue:
    """Tests for _parse_multiline_value function."""

    def test_empty_string(self) -> None:
        """Should return empty list for empty string."""
        assert _parse_multiline_value("") == []

    def test_whitespace_only(self) -> None:
        """Should return empty list for whitespace only."""
        assert _parse_multiline_value("   ") == []

    def test_space_separated(self) -> None:
        """Should parse space-separated values."""
        result = _parse_multiline_value("git curl wget")
        assert result == ["git", "curl", "wget"]

    def test_quoted_strings(self) -> None:
        """Should parse quoted strings (multiline hooks style)."""
        result = _parse_multiline_value('"echo hello" "echo world"')
        assert result == ["echo hello", "echo world"]

    def test_single_quoted_string(self) -> None:
        """Should parse single quoted string."""
        result = _parse_multiline_value('"echo hello"')
        assert result == ["echo hello"]


class TestParseAssembleFile:
    """Tests for parse_assemble_file function."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Should raise ValueError when file not found."""
        with pytest.raises(ValueError, match="not found"):
            parse_assemble_file(tmp_path / "nonexistent.ini", "test")

    def test_section_not_found(self, tmp_path: Path) -> None:
        """Should raise ValueError when section not found."""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text("[other]\nimage=alpine\n")
        with pytest.raises(ValueError, match="not found"):
            parse_assemble_file(ini_file, "mycontainer")

    def test_parse_basic_config(self, tmp_path: Path) -> None:
        """Should parse basic container config."""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text("""[mycontainer]
image=alpine:latest
additional_packages=git curl
""")
        result = parse_assemble_file(ini_file, "mycontainer")

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
        result = parse_assemble_file(ini_file, "mycontainer")

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
        result = parse_assemble_file(ini_file, "mycontainer")

        assert "volume" in result.remaining_options
        assert "nvidia" in result.remaining_options
        assert "image" not in result.remaining_options


class TestGenerateAssembleContent:
    """Tests for generate_assemble_content function."""

    def test_basic_content(self) -> None:
        """Should generate basic INI content."""
        config = ContainerConfig(
            name="test",
            image="old:image",
            remaining_options={"volume": ["/home:/home"]},
        )
        result = generate_assemble_content(config, "test:latest")

        assert "[test]" in result
        assert "image=test:latest" in result
        assert "volume=/home:/home" in result

    def test_no_baked_fields_in_output(self) -> None:
        """Should not include baked fields in output."""
        config = ContainerConfig(
            name="test",
            image="old:image",
            additional_packages=["git"],
            init_hooks=["echo hello"],
        )
        result = generate_assemble_content(config, "test:latest")

        assert "additional_packages" not in result
        assert "init_hooks" not in result
        assert "pre_init_hooks" not in result


class TestGenerateContainerfile:
    """Tests for generate_containerfile function."""

    def test_always_includes_upgrade_and_install(self) -> None:
        """Should always include upgrade and install steps."""
        result = generate_containerfile(
            "alpine:latest",
            has_pre_hooks=False,
            has_packages=False,
            has_hooks=False,
        )

        assert "FROM alpine:latest" in result
        assert "upgrade.sh" in result
        assert "install.sh" in result

    def test_includes_pre_hooks_when_present(self) -> None:
        """Should include pre_init_hooks step when has_pre_hooks=True."""
        result = generate_containerfile(
            "alpine:latest",
            has_pre_hooks=True,
            has_packages=False,
            has_hooks=False,
        )

        assert "pre_init_hooks.sh" in result

    def test_excludes_pre_hooks_when_absent(self) -> None:
        """Should not include pre_init_hooks step when has_pre_hooks=False."""
        result = generate_containerfile(
            "alpine:latest",
            has_pre_hooks=False,
            has_packages=False,
            has_hooks=False,
        )

        assert "pre_init_hooks.sh" not in result

    def test_includes_packages_when_present(self) -> None:
        """Should include additional_packages step when has_packages=True."""
        result = generate_containerfile(
            "alpine:latest",
            has_pre_hooks=False,
            has_packages=True,
            has_hooks=False,
        )

        assert "additional_packages.sh" in result

    def test_excludes_packages_when_absent(self) -> None:
        """Should not include additional_packages step when has_packages=False."""
        result = generate_containerfile(
            "alpine:latest",
            has_pre_hooks=False,
            has_packages=False,
            has_hooks=False,
        )

        assert "additional_packages.sh" not in result

    def test_includes_hooks_when_present(self) -> None:
        """Should include init_hooks step when has_hooks=True."""
        result = generate_containerfile(
            "alpine:latest",
            has_pre_hooks=False,
            has_packages=False,
            has_hooks=True,
        )

        assert "init_hooks.sh" in result

    def test_excludes_hooks_when_absent(self) -> None:
        """Should not include init_hooks step when has_hooks=False."""
        result = generate_containerfile(
            "alpine:latest",
            has_pre_hooks=False,
            has_packages=False,
            has_hooks=False,
        )

        assert "init_hooks.sh" not in result

    def test_all_steps_in_correct_order(self) -> None:
        """Should include all steps in correct order when all are present."""
        result = generate_containerfile(
            "alpine:latest",
            has_pre_hooks=True,
            has_packages=True,
            has_hooks=True,
        )

        # Check order by finding COPY command positions (more specific)
        upgrade_pos = result.find("COPY upgrade.sh")
        pre_hooks_pos = result.find("COPY pre_init_hooks.sh")
        install_pos = result.find("COPY install.sh")
        packages_pos = result.find("COPY additional_packages.sh")
        hooks_pos = result.find("COPY init_hooks.sh")

        assert upgrade_pos < pre_hooks_pos < install_pos < packages_pos < hooks_pos


class TestRunAssemble:
    """Tests for run_assemble function."""

    def test_returns_error_when_config_not_found(self, tmp_path: Path) -> None:
        """Should return error when optimized config doesn't exist."""
        with patch(
            "distrobox_boost.command.assemble.get_container_cache_dir",
            return_value=tmp_path / "nonexistent",
        ):
            result = run_assemble("mycontainer", ["create"])
            assert result == 1

    def test_passes_create_to_distrobox(self, tmp_path: Path) -> None:
        """Should pass 'create' command to distrobox assemble."""
        config_file = tmp_path / "distrobox.ini"
        config_file.write_text("[test]\nimage=test:latest\n")

        with (
            patch(
                "distrobox_boost.command.assemble.get_container_cache_dir",
                return_value=tmp_path,
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            run_assemble("test", ["create"])

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert cmd[:3] == ["distrobox", "assemble", "create"]
            assert "--file" in cmd
            assert str(config_file) in cmd

    def test_passes_rm_to_distrobox(self, tmp_path: Path) -> None:
        """Should pass 'rm' command to distrobox assemble."""
        config_file = tmp_path / "distrobox.ini"
        config_file.write_text("[test]\nimage=test:latest\n")

        with (
            patch(
                "distrobox_boost.command.assemble.get_container_cache_dir",
                return_value=tmp_path,
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            run_assemble("test", ["rm"])

            cmd = mock_run.call_args[0][0]
            assert cmd[:3] == ["distrobox", "assemble", "rm"]
            assert "--file" in cmd

    def test_passes_replace_to_distrobox(self, tmp_path: Path) -> None:
        """Should pass 'replace' command to distrobox assemble."""
        config_file = tmp_path / "distrobox.ini"
        config_file.write_text("[test]\nimage=test:latest\n")

        with (
            patch(
                "distrobox_boost.command.assemble.get_container_cache_dir",
                return_value=tmp_path,
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            run_assemble("test", ["replace"])

            cmd = mock_run.call_args[0][0]
            assert cmd[:3] == ["distrobox", "assemble", "replace"]
            assert "--file" in cmd

    def test_passes_extra_flags_to_distrobox(self, tmp_path: Path) -> None:
        """Should pass extra flags like --dry-run to distrobox assemble."""
        config_file = tmp_path / "distrobox.ini"
        config_file.write_text("[test]\nimage=test:latest\n")

        with (
            patch(
                "distrobox_boost.command.assemble.get_container_cache_dir",
                return_value=tmp_path,
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            run_assemble("test", ["create", "--dry-run"])

            cmd = mock_run.call_args[0][0]
            assert "create" in cmd
            assert "--dry-run" in cmd
            assert "--file" in cmd

    def test_returns_distrobox_exit_code(self, tmp_path: Path) -> None:
        """Should return the exit code from distrobox assemble."""
        config_file = tmp_path / "distrobox.ini"
        config_file.write_text("[test]\nimage=test:latest\n")

        with (
            patch(
                "distrobox_boost.command.assemble.get_container_cache_dir",
                return_value=tmp_path,
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 42
            result = run_assemble("test", ["create"])

            assert result == 42

    def test_empty_passthrough_args(self, tmp_path: Path) -> None:
        """Should work with empty passthrough args."""
        config_file = tmp_path / "distrobox.ini"
        config_file.write_text("[test]\nimage=test:latest\n")

        with (
            patch(
                "distrobox_boost.command.assemble.get_container_cache_dir",
                return_value=tmp_path,
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            run_assemble("test", [])

            cmd = mock_run.call_args[0][0]
            assert cmd[:2] == ["distrobox", "assemble"]
            assert "--file" in cmd
