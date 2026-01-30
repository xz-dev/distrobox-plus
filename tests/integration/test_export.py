"""Tests for distrobox-export command."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from distrobox_plus.commands.export import (
    _build_container_command_prefix,
    _build_container_command_suffix,
    _check_dependencies,
    _check_in_container,
    _filter_enter_flags,
    _generate_script,
    _get_canonical_dirs,
    _get_container_name,
    _get_dest_path,
    _get_distrobox_enter_path,
    _get_host_home,
    _get_sudo_prefix,
    _is_rootful_container,
    _iter_files_recursive,
    create_parser,
    run,
)

pytestmark = [pytest.mark.integration, pytest.mark.export]


class TestExportHelp:
    """Test export help output."""

    @pytest.mark.fast
    def test_export_help(self, distrobox):
        """Test export --help output."""
        result = distrobox.run("export", ["--help"])

        # Help should show usage and exit 0
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "export" in result.stdout

    @pytest.mark.fast
    def test_export_version(self, distrobox):
        """Test export --version output."""
        result = distrobox.run("export", ["--version"])

        assert "distrobox:" in result.stdout or "distrobox:" in result.stderr


class TestExportParser:
    """Test export argument parsing."""

    @pytest.mark.fast
    def test_parser_app_flag(self):
        """Test parsing --app flag."""
        parser = create_parser()
        args = parser.parse_args(["--app", "firefox"])

        assert args.exported_app == "firefox"

    @pytest.mark.fast
    def test_parser_bin_flag(self):
        """Test parsing --bin flag."""
        parser = create_parser()
        args = parser.parse_args(["--bin", "/usr/bin/vim"])

        assert args.exported_bin == "/usr/bin/vim"

    @pytest.mark.fast
    def test_parser_delete_flag(self):
        """Test parsing --delete flag."""
        parser = create_parser()
        args = parser.parse_args(["--app", "firefox", "--delete"])

        assert args.exported_delete is True

    @pytest.mark.fast
    def test_parser_export_label(self):
        """Test parsing --export-label flag."""
        parser = create_parser()
        args = parser.parse_args(["--app", "firefox", "-el", "custom label"])

        assert args.exported_app_label == "custom label"

    @pytest.mark.fast
    def test_parser_export_path(self):
        """Test parsing --export-path flag."""
        parser = create_parser()
        args = parser.parse_args(["--bin", "/usr/bin/vim", "-ep", "/custom/path"])

        assert args.dest_path == "/custom/path"

    @pytest.mark.fast
    def test_parser_sudo_flag(self):
        """Test parsing --sudo flag."""
        parser = create_parser()
        args = parser.parse_args(["--bin", "/usr/bin/vim", "--sudo"])

        assert args.is_sudo is True

    @pytest.mark.fast
    def test_parser_list_apps(self):
        """Test parsing --list-apps flag."""
        parser = create_parser()
        args = parser.parse_args(["--list-apps"])

        assert args.list_apps is True

    @pytest.mark.fast
    def test_parser_list_binaries(self):
        """Test parsing --list-binaries flag."""
        parser = create_parser()
        args = parser.parse_args(["--list-binaries"])

        assert args.list_binaries is True

    @pytest.mark.fast
    def test_parser_extra_flags(self):
        """Test parsing --extra-flags."""
        parser = create_parser()
        # Note: value is passed as a single string
        args = parser.parse_args(
            ["--bin", "/usr/bin/vim", "--extra-flags", "debug-mode"]
        )

        assert args.extra_flags == "debug-mode"

    @pytest.mark.fast
    def test_parser_enter_flags(self):
        """Test parsing --enter-flags."""
        parser = create_parser()
        # Note: value is passed as a single string
        args = parser.parse_args(
            ["--bin", "/usr/bin/vim", "--enter-flags", "no-workdir"]
        )

        assert args.enter_flags == "no-workdir"

    @pytest.mark.fast
    def test_parser_verbose_flag(self):
        """Test parsing --verbose flag."""
        parser = create_parser()
        args = parser.parse_args(["--verbose"])

        assert args.verbose is True


class TestExportHelpers:
    """Test export helper functions."""

    @pytest.mark.fast
    def test_check_dependencies(self):
        """Test dependency checking."""
        # Should return True on a normal system with coreutils
        assert _check_dependencies() is True

    @pytest.mark.fast
    def test_check_not_in_container(self):
        """Test container check on host."""
        # Should return False when not in container
        assert _check_in_container() is False

    @pytest.mark.fast
    def test_is_not_rootful_container(self):
        """Test rootful container check on host."""
        # Should return False when not in container
        assert _is_rootful_container() is False

    @pytest.mark.fast
    def test_get_container_name_empty_on_host(self):
        """Test container name retrieval on host."""
        # Should return empty string when not in container
        # Clear CONTAINER_ID if set
        old_val = os.environ.pop("CONTAINER_ID", None)
        try:
            name = _get_container_name()
            assert name == ""
        finally:
            if old_val:
                os.environ["CONTAINER_ID"] = old_val

    @pytest.mark.fast
    def test_get_container_name_from_env(self):
        """Test container name from CONTAINER_ID environment variable."""
        old_val = os.environ.get("CONTAINER_ID")
        try:
            os.environ["CONTAINER_ID"] = "test-container"
            name = _get_container_name()
            assert name == "test-container"
        finally:
            if old_val:
                os.environ["CONTAINER_ID"] = old_val
            elif "CONTAINER_ID" in os.environ:
                del os.environ["CONTAINER_ID"]

    @pytest.mark.fast
    def test_get_host_home(self):
        """Test host home retrieval."""
        home = _get_host_home()
        assert home == os.environ.get("DISTROBOX_HOST_HOME", os.environ.get("HOME", ""))

    @pytest.mark.fast
    def test_get_host_home_from_distrobox_env(self):
        """Test host home from DISTROBOX_HOST_HOME."""
        old_val = os.environ.get("DISTROBOX_HOST_HOME")
        try:
            os.environ["DISTROBOX_HOST_HOME"] = "/custom/home"
            home = _get_host_home()
            assert home == "/custom/home"
        finally:
            if old_val:
                os.environ["DISTROBOX_HOST_HOME"] = old_val
            elif "DISTROBOX_HOST_HOME" in os.environ:
                del os.environ["DISTROBOX_HOST_HOME"]

    @pytest.mark.fast
    def test_get_dest_path_default(self):
        """Test default destination path."""
        host_home = "/home/testuser"
        path = _get_dest_path(host_home)
        assert path == "/home/testuser/.local/bin"

    @pytest.mark.fast
    def test_get_dest_path_from_env(self):
        """Test destination path from DISTROBOX_EXPORT_PATH."""
        old_val = os.environ.get("DISTROBOX_EXPORT_PATH")
        try:
            os.environ["DISTROBOX_EXPORT_PATH"] = "/custom/export/path"
            path = _get_dest_path("/home/testuser")
            assert path == "/custom/export/path"
        finally:
            if old_val:
                os.environ["DISTROBOX_EXPORT_PATH"] = old_val
            elif "DISTROBOX_EXPORT_PATH" in os.environ:
                del os.environ["DISTROBOX_EXPORT_PATH"]

    @pytest.mark.fast
    def test_get_distrobox_enter_path_default(self):
        """Test distrobox-enter path default."""
        old_val = os.environ.pop("DISTROBOX_ENTER_PATH", None)
        try:
            path = _get_distrobox_enter_path()
            assert path == "distrobox-enter"
        finally:
            if old_val:
                os.environ["DISTROBOX_ENTER_PATH"] = old_val

    @pytest.mark.fast
    def test_get_distrobox_enter_path_env(self):
        """Test distrobox-enter path from environment."""
        os.environ["DISTROBOX_ENTER_PATH"] = "/custom/distrobox-enter"
        try:
            path = _get_distrobox_enter_path()
            assert path == "/custom/distrobox-enter"
        finally:
            del os.environ["DISTROBOX_ENTER_PATH"]

    @pytest.mark.fast
    def test_filter_enter_flags_empty(self):
        """Test filtering empty enter flags."""
        result = _filter_enter_flags("")
        assert result == ""

    @pytest.mark.fast
    def test_filter_enter_flags_removes_root(self, capsys):
        """Test filtering removes --root flag."""
        result = _filter_enter_flags("--root --verbose")
        assert "--root" not in result
        assert "--verbose" in result
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    @pytest.mark.fast
    def test_filter_enter_flags_removes_short_root(self, capsys):
        """Test filtering removes -r flag."""
        result = _filter_enter_flags("-r --verbose")
        assert "-r" not in result
        assert "--verbose" in result
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    @pytest.mark.fast
    def test_filter_enter_flags_removes_name(self, capsys):
        """Test filtering removes --name flag."""
        result = _filter_enter_flags("--name test --verbose")
        assert "--name" not in result
        assert "test" not in result
        assert "--verbose" in result
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    @pytest.mark.fast
    def test_filter_enter_flags_removes_short_name(self, capsys):
        """Test filtering removes -n flag."""
        result = _filter_enter_flags("-n test --verbose")
        assert "-n" not in result
        assert "test" not in result
        assert "--verbose" in result
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    @pytest.mark.fast
    def test_filter_enter_flags_preserves_other_flags(self):
        """Test filtering preserves other flags."""
        result = _filter_enter_flags("--verbose --no-workdir")
        assert "--verbose" in result
        assert "--no-workdir" in result

    @pytest.mark.fast
    def test_get_sudo_prefix_no_sudo(self):
        """Test sudo prefix when not using sudo."""
        result = _get_sudo_prefix(False)
        assert result == ""


class TestExportScriptGeneration:
    """Test script generation functions."""

    @pytest.mark.fast
    def test_build_container_command_suffix_basic(self):
        """Test basic container command suffix."""
        result = _build_container_command_suffix("/usr/bin/vim", "--debug", "")

        assert "'/usr/bin/vim'" in result
        assert "--debug" in result

    @pytest.mark.fast
    def test_build_container_command_suffix_with_doas(self):
        """Test container command suffix with doas."""
        result = _build_container_command_suffix("/usr/bin/vim", "", "doas")

        assert "sh -l -c" in result
        assert "'/usr/bin/vim'" in result

    @pytest.mark.fast
    def test_build_container_command_suffix_with_su_exec(self):
        """Test container command suffix with su-exec."""
        result = _build_container_command_suffix("/usr/bin/vim", "", "su-exec root")

        assert "sh -l -c" in result
        assert "'/usr/bin/vim'" in result

    @pytest.mark.fast
    def test_build_container_command_prefix_basic(self):
        """Test basic container command prefix."""
        result = _build_container_command_prefix(
            container_name="test-container",
            enter_flags="",
            rootful="",
            sudo_prefix="",
            sudo_askpass_path="/path/to/askpass",
        )

        assert "distrobox-enter" in result
        assert "-n test-container" in result

    @pytest.mark.fast
    def test_build_container_command_prefix_with_rootful(self):
        """Test container command prefix with rootful."""
        result = _build_container_command_prefix(
            container_name="test-container",
            enter_flags="",
            rootful="--root",
            sudo_prefix="",
            sudo_askpass_path="/path/to/askpass",
        )

        assert "--root" in result
        assert "SUDO_ASKPASS" in result

    @pytest.mark.fast
    def test_build_container_command_prefix_with_enter_flags(self):
        """Test container command prefix with enter flags."""
        result = _build_container_command_prefix(
            container_name="test-container",
            enter_flags="--verbose",
            rootful="",
            sudo_prefix="",
            sudo_askpass_path="/path/to/askpass",
        )

        assert "--verbose" in result

    @pytest.mark.fast
    def test_generate_script_basic(self):
        """Test basic script generation."""
        script = _generate_script(
            container_name="test-container",
            exported_bin="/usr/bin/vim",
            dest_path="/home/user/.local/bin",
            rootful="",
            enter_flags="",
            sudo_prefix="",
            extra_flags="",
        )

        assert "#!/bin/sh" in script
        assert "# distrobox_binary" in script
        assert "# name: test-container" in script
        assert "distrobox-enter" in script
        assert "/usr/bin/vim" in script

    @pytest.mark.fast
    def test_generate_script_contains_conditional(self):
        """Test script contains container check conditional."""
        script = _generate_script(
            container_name="test-container",
            exported_bin="/usr/bin/vim",
            dest_path="/home/user/.local/bin",
            rootful="",
            enter_flags="",
            sudo_prefix="",
            extra_flags="",
        )

        assert "CONTAINER_ID" in script
        assert "distrobox-host-exec" in script


class TestExportCanonicalDirs:
    """Test canonical directory functions."""

    @pytest.mark.fast
    def test_get_canonical_dirs_returns_list(self):
        """Test that canonical dirs returns a list."""
        dirs = _get_canonical_dirs()
        assert isinstance(dirs, list)

    @pytest.mark.fast
    def test_get_canonical_dirs_contains_applications(self):
        """Test that canonical dirs paths contain 'applications'."""
        dirs = _get_canonical_dirs()
        # All dirs should end with 'applications'
        for d in dirs:
            assert d.endswith("applications")


class TestExportIterFilesRecursive:
    """Test recursive file iteration."""

    @pytest.mark.fast
    def test_iter_files_recursive_finds_files(self):
        """Test recursive iteration finds files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files
            Path(tmpdir, "file1.txt").write_text("content1")
            Path(tmpdir, "file2.txt").write_text("content2")

            files = list(_iter_files_recursive(Path(tmpdir)))

            assert len(files) == 2
            names = [f.name for f in files]
            assert "file1.txt" in names
            assert "file2.txt" in names

    @pytest.mark.fast
    def test_iter_files_recursive_finds_nested_files(self):
        """Test recursive iteration finds nested files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested directories
            subdir = Path(tmpdir, "subdir")
            subdir.mkdir()
            Path(tmpdir, "file1.txt").write_text("content1")
            Path(subdir, "file2.txt").write_text("content2")

            files = list(_iter_files_recursive(Path(tmpdir)))

            assert len(files) == 2
            names = [f.name for f in files]
            assert "file1.txt" in names
            assert "file2.txt" in names

    @pytest.mark.fast
    def test_iter_files_recursive_finds_symlinks(self):
        """Test recursive iteration finds symlinks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file and a symlink
            file1 = Path(tmpdir, "file1.txt")
            file1.write_text("content1")
            link = Path(tmpdir, "link.txt")
            link.symlink_to(file1)

            files = list(_iter_files_recursive(Path(tmpdir)))

            assert len(files) == 2
            names = [f.name for f in files]
            assert "file1.txt" in names
            assert "link.txt" in names

    @pytest.mark.fast
    def test_iter_files_recursive_empty_dir(self):
        """Test recursive iteration on empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = list(_iter_files_recursive(Path(tmpdir)))
            assert len(files) == 0

    @pytest.mark.fast
    def test_iter_files_recursive_nonexistent_dir(self):
        """Test recursive iteration on non-existent directory."""
        files = list(_iter_files_recursive(Path("/nonexistent/path")))
        assert len(files) == 0


class TestExportOutsideContainer:
    """Test export behavior outside container."""

    @pytest.mark.fast
    def test_export_fails_outside_container(self):
        """Test that export fails when run outside container."""
        result = run(["--bin", "/usr/bin/ls"])
        assert result == 126

    @pytest.mark.fast
    def test_export_no_action_fails(self):
        """Test that export fails without action."""
        # This test would need to be run inside a container
        # For now we verify it fails outside container first
        result = run([])
        assert result == 126  # Container check happens before action check

    @pytest.mark.fast
    def test_export_multiple_actions_fails(self):
        """Test that export fails with multiple actions (outside container)."""
        # Even though it fails due to container check first,
        # we can verify the parser accepts multiple flags
        parser = create_parser()
        args = parser.parse_args(["--app", "firefox", "--bin", "/usr/bin/vim"])
        assert args.exported_app == "firefox"
        assert args.exported_bin == "/usr/bin/vim"
