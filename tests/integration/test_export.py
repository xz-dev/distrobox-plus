"""Tests for distrobox-export command."""

from __future__ import annotations

import pytest

from distrobox_plus.commands.export import (
    _check_dependencies,
    _check_in_container,
    _filter_enter_flags,
    _get_container_name,
    _get_distrobox_enter_path,
    _get_host_home,
    _get_sudo_prefix,
    _is_rootful_container,
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

        # Help should contain key information
        assert "distrobox version:" in result.stdout or "distrobox version:" in result.stderr
        assert "--app" in result.stdout or "--app" in result.stderr
        assert "--bin" in result.stdout or "--bin" in result.stderr
        assert "--delete" in result.stdout or "--delete" in result.stderr

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
        import os
        # Clear CONTAINER_ID if set
        old_val = os.environ.pop("CONTAINER_ID", None)
        try:
            name = _get_container_name()
            assert name == ""
        finally:
            if old_val:
                os.environ["CONTAINER_ID"] = old_val

    @pytest.mark.fast
    def test_get_host_home(self):
        """Test host home retrieval."""
        import os
        home = _get_host_home()
        assert home == os.environ.get("DISTROBOX_HOST_HOME", os.environ.get("HOME", ""))

    @pytest.mark.fast
    def test_get_distrobox_enter_path_default(self):
        """Test distrobox-enter path default."""
        import os
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
        import os
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
    def test_filter_enter_flags_removes_name(self, capsys):
        """Test filtering removes --name flag."""
        result = _filter_enter_flags("--name test --verbose")
        assert "--name" not in result
        assert "test" not in result
        assert "--verbose" in result
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    @pytest.mark.fast
    def test_get_sudo_prefix_no_sudo(self):
        """Test sudo prefix when not using sudo."""
        result = _get_sudo_prefix(False)
        assert result == ""


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
