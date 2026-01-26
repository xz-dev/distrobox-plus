"""Tests for utils/hijack.py."""

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from distrobox_boost.utils.hijack import HijackManager


class TestHijackManagerInit:
    """Tests for HijackManager initialization."""

    def test_init_creates_instance(self) -> None:
        """Should create HijackManager instance."""
        manager = HijackManager()
        assert manager._tmpdir is None
        assert manager._hijack_dir is None

    def test_hijack_dir_raises_before_enter(self) -> None:
        """Should raise RuntimeError when accessing hijack_dir before entering."""
        manager = HijackManager()
        with pytest.raises(RuntimeError, match="not entered as context manager"):
            _ = manager.hijack_dir

    def test_assemble_path_raises_before_enter(self) -> None:
        """Should raise RuntimeError when accessing assemble_path before entering."""
        manager = HijackManager()
        with pytest.raises(RuntimeError, match="not entered as context manager"):
            _ = manager.assemble_path


class TestHijackManagerContextManager:
    """Tests for HijackManager as context manager."""

    @patch("shutil.which")
    def test_creates_temp_directory(self, mock_which: patch) -> None:
        """Should create a temporary directory on enter."""
        mock_which.return_value = "/usr/bin/distrobox-assemble"

        with HijackManager() as hijack:
            assert hijack._tmpdir is not None
            assert hijack._hijack_dir is not None
            assert hijack._hijack_dir.exists()
            assert hijack._hijack_dir.is_dir()

    @patch("shutil.which")
    def test_temp_dir_has_correct_prefix(self, mock_which: patch) -> None:
        """Should create temp directory with distrobox-boost prefix."""
        mock_which.return_value = "/usr/bin/distrobox-assemble"

        with HijackManager() as hijack:
            assert "distrobox-boost" in str(hijack._hijack_dir)

    @patch("shutil.which")
    def test_symlinks_distrobox_assemble(self, mock_which: patch) -> None:
        """Should create symlink to real distrobox-assemble."""
        mock_which.return_value = "/usr/bin/distrobox-assemble"

        with HijackManager() as hijack:
            assemble_link = hijack._hijack_dir / "distrobox-assemble"
            assert assemble_link.exists() or assemble_link.is_symlink()
            assert os.path.islink(assemble_link)
            assert os.readlink(assemble_link) == "/usr/bin/distrobox-assemble"

    @patch("shutil.which")
    def test_creates_distrobox_create_interceptor(self, mock_which: patch) -> None:
        """Should create interceptor script for distrobox-create."""
        mock_which.return_value = "/usr/bin/distrobox-assemble"

        with HijackManager() as hijack:
            interceptor = hijack._hijack_dir / "distrobox-create"
            assert interceptor.exists()
            content = interceptor.read_text()
            assert "distrobox-boost create" in content

    @patch("shutil.which")
    def test_creates_distrobox_router(self, mock_which: patch) -> None:
        """Should create router script for distrobox command."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "distrobox-assemble":
                return "/usr/bin/distrobox-assemble"
            elif cmd == "distrobox":
                return "/usr/bin/distrobox"
            return None

        mock_which.side_effect = which_side_effect

        with HijackManager() as hijack:
            router = hijack._hijack_dir / "distrobox"
            assert router.exists()
            content = router.read_text()
            assert "distrobox-boost create" in content
            assert 'if [ "$1" = "create" ]' in content

    @patch("shutil.which")
    def test_scripts_are_executable(self, mock_which: patch) -> None:
        """Should make interceptor scripts executable."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "distrobox-assemble":
                return "/usr/bin/distrobox-assemble"
            elif cmd == "distrobox":
                return "/usr/bin/distrobox"
            return None

        mock_which.side_effect = which_side_effect

        with HijackManager() as hijack:
            for script_name in ["distrobox-create", "distrobox"]:
                script = hijack._hijack_dir / script_name
                assert script.exists()
                mode = script.stat().st_mode
                assert mode & stat.S_IXUSR, f"{script_name} should be user executable"
                assert mode & stat.S_IXGRP, f"{script_name} should be group executable"
                assert mode & stat.S_IXOTH, f"{script_name} should be other executable"

    @patch("shutil.which")
    def test_creates_passthrough_scripts(self, mock_which: patch) -> None:
        """Should create passthrough scripts for other distrobox commands."""
        def which_side_effect(cmd: str) -> str | None:
            mapping = {
                "distrobox-assemble": "/usr/bin/distrobox-assemble",
                "distrobox": "/usr/bin/distrobox",
                "distrobox-list": "/usr/bin/distrobox-list",
                "distrobox-enter": "/usr/bin/distrobox-enter",
                "distrobox-rm": "/usr/bin/distrobox-rm",
                "distrobox-stop": "/usr/bin/distrobox-stop",
            }
            return mapping.get(cmd)

        mock_which.side_effect = which_side_effect

        with HijackManager() as hijack:
            for cmd in ["distrobox-list", "distrobox-enter", "distrobox-rm", "distrobox-stop"]:
                script = hijack._hijack_dir / cmd
                assert script.exists(), f"{cmd} passthrough should exist"
                content = script.read_text()
                # Should exec the real command, not distrobox-boost
                assert "distrobox-boost" not in content
                assert f"/usr/bin/{cmd}" in content

    @patch("shutil.which")
    def test_cleanup_on_exit(self, mock_which: patch) -> None:
        """Should clean up temporary directory on exit."""
        mock_which.return_value = "/usr/bin/distrobox-assemble"

        with HijackManager() as hijack:
            tmpdir_path = hijack._hijack_dir
            assert tmpdir_path.exists()

        # After exiting context
        assert not tmpdir_path.exists()

    @patch("shutil.which")
    def test_cleanup_on_exception(self, mock_which: patch) -> None:
        """Should clean up temporary directory even when exception occurs."""
        mock_which.return_value = "/usr/bin/distrobox-assemble"

        tmpdir_path = None
        try:
            with HijackManager() as hijack:
                tmpdir_path = hijack._hijack_dir
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert tmpdir_path is not None
        assert not tmpdir_path.exists()

    @patch("shutil.which")
    def test_hijack_dir_is_none_after_exit(self, mock_which: patch) -> None:
        """Should set internal state to None after exit."""
        mock_which.return_value = "/usr/bin/distrobox-assemble"

        manager = HijackManager()
        with manager:
            pass

        assert manager._tmpdir is None
        assert manager._hijack_dir is None

    @patch("shutil.which")
    def test_assemble_path_property(self, mock_which: patch) -> None:
        """Should return correct path for distrobox-assemble."""
        mock_which.return_value = "/usr/bin/distrobox-assemble"

        with HijackManager() as hijack:
            expected = hijack._hijack_dir / "distrobox-assemble"
            assert hijack.assemble_path == expected


class TestHijackManagerErrors:
    """Tests for HijackManager error handling."""

    @patch("shutil.which")
    def test_raises_when_assemble_not_found(self, mock_which: patch) -> None:
        """Should raise RuntimeError when distrobox-assemble not in PATH."""
        mock_which.return_value = None

        with pytest.raises(RuntimeError, match="distrobox-assemble not found"):
            with HijackManager():
                pass

    @patch("shutil.which")
    def test_raises_when_distrobox_not_found(self, mock_which: patch) -> None:
        """Should raise RuntimeError when distrobox not in PATH."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "distrobox-assemble":
                return "/usr/bin/distrobox-assemble"
            return None

        mock_which.side_effect = which_side_effect

        with pytest.raises(RuntimeError, match="distrobox not found"):
            with HijackManager():
                pass


class TestDistroboxRouterScript:
    """Tests for distrobox router script content."""

    @patch("shutil.which")
    def test_router_intercepts_create_subcommand(self, mock_which: patch) -> None:
        """Should intercept 'create' subcommand."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "distrobox-assemble":
                return "/usr/bin/distrobox-assemble"
            elif cmd == "distrobox":
                return "/usr/bin/distrobox"
            return None

        mock_which.side_effect = which_side_effect

        with HijackManager() as hijack:
            router = hijack._hijack_dir / "distrobox"
            content = router.read_text()
            # Check script routes create to distrobox-boost
            assert '[ "$1" = "create" ]' in content
            assert "shift" in content
            assert 'exec distrobox-boost create "$@"' in content

    @patch("shutil.which")
    def test_router_passes_other_commands(self, mock_which: patch) -> None:
        """Should pass non-create commands to real distrobox."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "distrobox-assemble":
                return "/usr/bin/distrobox-assemble"
            elif cmd == "distrobox":
                return "/usr/bin/distrobox"
            return None

        mock_which.side_effect = which_side_effect

        with HijackManager() as hijack:
            router = hijack._hijack_dir / "distrobox"
            content = router.read_text()
            # Check script has else branch for other commands
            assert "else" in content
            assert '"/usr/bin/distrobox" "$@"' in content


class TestInterceptorScript:
    """Tests for interceptor script content."""

    @patch("shutil.which")
    def test_intercept_script_routes_to_boost(self, mock_which: patch) -> None:
        """Should route intercepted command to distrobox-boost."""
        mock_which.return_value = "/usr/bin/distrobox-assemble"

        with HijackManager() as hijack:
            interceptor = hijack._hijack_dir / "distrobox-create"
            content = interceptor.read_text()
            assert content.startswith("#!/bin/sh\n")
            assert 'exec distrobox-boost create "$@"' in content

    @patch("shutil.which")
    def test_passthrough_script_uses_real_command(self, mock_which: patch) -> None:
        """Should pass through to real command."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "distrobox-assemble":
                return "/usr/bin/distrobox-assemble"
            elif cmd == "distrobox":
                return "/usr/bin/distrobox"
            elif cmd == "distrobox-list":
                return "/usr/bin/distrobox-list"
            return None

        mock_which.side_effect = which_side_effect

        with HijackManager() as hijack:
            passthrough = hijack._hijack_dir / "distrobox-list"
            content = passthrough.read_text()
            assert content.startswith("#!/bin/sh\n")
            assert 'exec "/usr/bin/distrobox-list" "$@"' in content

    @patch("shutil.which")
    def test_missing_command_creates_error_script(self, mock_which: patch) -> None:
        """Should create error script when passthrough command not found."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "distrobox-assemble":
                return "/usr/bin/distrobox-assemble"
            elif cmd == "distrobox":
                return "/usr/bin/distrobox"
            # Return None for passthrough commands to simulate not found
            return None

        mock_which.side_effect = which_side_effect

        with HijackManager() as hijack:
            # distrobox-list is not found
            passthrough = hijack._hijack_dir / "distrobox-list"
            content = passthrough.read_text()
            assert "Error:" in content
            assert "not found" in content
            assert "exit 1" in content
