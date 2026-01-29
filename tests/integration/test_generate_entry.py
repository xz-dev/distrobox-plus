"""Tests for distrobox-generate-entry command."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from distrobox_plus.commands.generate_entry import (
    _capitalize_first,
    _generate_desktop_entry,
    _get_applications_dir,
    _get_default_icon_path,
    _get_download_command,
    _get_icons_dir,
    _get_xdg_data_home,
    create_parser,
    run,
)

pytestmark = [pytest.mark.integration, pytest.mark.generate_entry]


class TestGenerateEntryHelp:
    """Test generate-entry help output."""

    @pytest.mark.fast
    def test_generate_entry_help(self, distrobox):
        """Test generate-entry --help output."""
        result = distrobox.run("generate-entry", ["--help"])

        # Help should show usage and exit 0
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "generate-entry" in result.stdout

    @pytest.mark.fast
    def test_generate_entry_version(self, distrobox):
        """Test generate-entry --version output."""
        result = distrobox.run("generate-entry", ["--version"])

        assert "distrobox:" in result.stdout or "distrobox:" in result.stderr


class TestGenerateEntryParser:
    """Test generate-entry argument parsing."""

    @pytest.mark.fast
    def test_parser_container_name(self):
        """Test parsing container name positional argument."""
        parser = create_parser()
        args = parser.parse_args(["my-container"])

        assert args.container_name == "my-container"

    @pytest.mark.fast
    def test_parser_default_container_name(self):
        """Test default container name."""
        parser = create_parser()
        args = parser.parse_args([])

        assert args.container_name == ""

    @pytest.mark.fast
    def test_parser_all_flag(self):
        """Test parsing --all flag."""
        parser = create_parser()
        args = parser.parse_args(["--all"])

        assert args.all_containers is True

    @pytest.mark.fast
    def test_parser_delete_flag(self):
        """Test parsing --delete flag."""
        parser = create_parser()
        args = parser.parse_args(["my-container", "--delete"])

        assert args.delete is True

    @pytest.mark.fast
    def test_parser_icon_flag(self):
        """Test parsing --icon flag."""
        parser = create_parser()
        args = parser.parse_args(["--icon", "/path/to/icon.png"])

        assert args.icon == "/path/to/icon.png"

    @pytest.mark.fast
    def test_parser_icon_default(self):
        """Test --icon default value."""
        parser = create_parser()
        args = parser.parse_args([])

        assert args.icon == "auto"

    @pytest.mark.fast
    def test_parser_root_flag(self):
        """Test parsing --root flag."""
        parser = create_parser()
        args = parser.parse_args(["--root"])

        assert args.root is True

    @pytest.mark.fast
    def test_parser_verbose_flag(self):
        """Test parsing --verbose flag."""
        parser = create_parser()
        args = parser.parse_args(["--verbose"])

        assert args.verbose is True


class TestGenerateEntryHelpers:
    """Test generate-entry helper functions."""

    @pytest.mark.fast
    def test_get_xdg_data_home(self):
        """Test XDG data home retrieval."""
        result = _get_xdg_data_home()
        assert isinstance(result, Path)
        # Should be a valid path
        assert str(result) != ""

    @pytest.mark.fast
    def test_get_default_icon_path(self):
        """Test default icon path."""
        result = _get_default_icon_path()
        assert isinstance(result, Path)
        assert result.name == "terminal-distrobox-icon.svg"
        assert "icons" in str(result)

    @pytest.mark.fast
    def test_get_applications_dir(self):
        """Test applications directory path."""
        result = _get_applications_dir()
        assert isinstance(result, Path)
        assert result.name == "applications"

    @pytest.mark.fast
    def test_get_icons_dir(self):
        """Test icons directory path."""
        result = _get_icons_dir()
        assert isinstance(result, Path)
        assert "icons" in str(result)
        assert "distrobox" in str(result)

    @pytest.mark.fast
    def test_capitalize_first_normal(self):
        """Test capitalizing first letter of normal string."""
        assert _capitalize_first("hello") == "Hello"
        assert _capitalize_first("world") == "World"

    @pytest.mark.fast
    def test_capitalize_first_already_capitalized(self):
        """Test capitalizing already capitalized string."""
        assert _capitalize_first("Hello") == "Hello"

    @pytest.mark.fast
    def test_capitalize_first_empty(self):
        """Test capitalizing empty string."""
        assert _capitalize_first("") == ""

    @pytest.mark.fast
    def test_capitalize_first_single_char(self):
        """Test capitalizing single character."""
        assert _capitalize_first("a") == "A"
        assert _capitalize_first("Z") == "Z"

    @pytest.mark.fast
    def test_capitalize_first_with_hyphen(self):
        """Test capitalizing string with hyphen."""
        assert _capitalize_first("my-container") == "My-container"

    @pytest.mark.fast
    def test_get_download_command_curl(self):
        """Test download command detection (curl)."""
        result = _get_download_command()
        # Should return curl or wget command list, or None
        if result is not None:
            assert isinstance(result, list)
            assert result[0] in ("curl", "wget")


class TestGenerateDesktopEntry:
    """Test desktop entry generation."""

    @pytest.mark.fast
    def test_generate_desktop_entry_basic(self):
        """Test basic desktop entry generation."""
        content = _generate_desktop_entry(
            container_name="test-container",
            icon="/path/to/icon.png",
            extra_flags="",
        )

        assert "[Desktop Entry]" in content
        assert "Name=Test-container" in content
        assert "Icon=/path/to/icon.png" in content
        assert "Terminal=true" in content
        assert "Type=Application" in content

    @pytest.mark.fast
    def test_generate_desktop_entry_with_root_flag(self):
        """Test desktop entry with --root flag."""
        content = _generate_desktop_entry(
            container_name="test-container",
            icon="/path/to/icon.png",
            extra_flags="--root",
        )

        assert "--root" in content
        assert "Exec=" in content

    @pytest.mark.fast
    def test_generate_desktop_entry_contains_actions(self):
        """Test that desktop entry contains remove action."""
        content = _generate_desktop_entry(
            container_name="test-container",
            icon="/path/to/icon.png",
            extra_flags="",
        )

        assert "[Desktop Action Remove]" in content
        assert "Name=Remove Test-container from system" in content

    @pytest.mark.fast
    def test_generate_desktop_entry_categories(self):
        """Test desktop entry categories."""
        content = _generate_desktop_entry(
            container_name="test-container",
            icon="/path/to/icon.png",
            extra_flags="",
        )

        assert "Categories=Distrobox;System;Utility" in content

    @pytest.mark.fast
    def test_generate_desktop_entry_keywords(self):
        """Test desktop entry keywords."""
        content = _generate_desktop_entry(
            container_name="test-container",
            icon="/path/to/icon.png",
            extra_flags="",
        )

        assert "Keywords=distrobox;" in content


class TestGenerateEntryRun:
    """Test generate-entry run function."""

    @pytest.mark.fast
    def test_run_nonexistent_container(self):
        """Test running with non-existent container."""
        result = run(["nonexistent-container-12345"])

        # Should fail because container doesn't exist
        assert result == 1

    @pytest.mark.fast
    def test_run_delete_nonexistent_entry(self):
        """Test deleting non-existent entry (should succeed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock the applications directory
            with mock.patch(
                "distrobox_plus.commands.generate_entry._get_applications_dir",
                return_value=Path(tmpdir),
            ):
                # Delete should succeed even if entry doesn't exist
                result = run(["nonexistent-container", "--delete"])
                assert result == 0
