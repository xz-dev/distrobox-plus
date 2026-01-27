"""Tests for utils/hijack.py."""

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from distrobox_boost.utils.hijack import DISTROBOX_COMMANDS, HijackManager


class TestDistroboxCommands:
    """Tests for DISTROBOX_COMMANDS constant."""

    def test_contains_core_commands(self) -> None:
        """Should contain all core distrobox commands."""
        expected = {"create", "assemble", "ephemeral", "enter", "rm", "stop", "list", "upgrade", "generate-entry"}
        assert set(DISTROBOX_COMMANDS) == expected


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

    def test_distrobox_path_raises_before_enter(self) -> None:
        """Should raise RuntimeError when accessing distrobox_path before entering."""
        manager = HijackManager()
        with pytest.raises(RuntimeError, match="not entered as context manager"):
            _ = manager.distrobox_path


class TestHijackManagerContextManager:
    """Tests for HijackManager as context manager."""

    def test_creates_temp_directory(self) -> None:
        """Should create a temporary directory on enter."""
        with HijackManager() as hijack:
            assert hijack._tmpdir is not None
            assert hijack._hijack_dir is not None
            assert hijack._hijack_dir.exists()
            assert hijack._hijack_dir.is_dir()

    def test_temp_dir_has_correct_prefix(self) -> None:
        """Should create temp directory with distrobox-boost prefix."""
        with HijackManager() as hijack:
            assert "distrobox-boost" in str(hijack._hijack_dir)

    def test_creates_interceptors_for_all_commands(self) -> None:
        """Should create interceptor scripts for all distrobox commands."""
        with HijackManager() as hijack:
            for cmd in DISTROBOX_COMMANDS:
                script = hijack._hijack_dir / f"distrobox-{cmd}"
                assert script.exists(), f"distrobox-{cmd} should exist"

    def test_interceptors_route_to_boost(self) -> None:
        """Should route intercepted commands to distrobox-boost."""
        with HijackManager() as hijack:
            for cmd in DISTROBOX_COMMANDS:
                script = hijack._hijack_dir / f"distrobox-{cmd}"
                content = script.read_text()
                assert f"exec distrobox-boost {cmd}" in content

    def test_creates_distrobox_router(self) -> None:
        """Should create router script for distrobox command."""
        with HijackManager() as hijack:
            router = hijack._hijack_dir / "distrobox"
            assert router.exists()
            content = router.read_text()
            # Check it routes known commands to distrobox-boost
            assert "distrobox-boost create" in content
            assert "distrobox-boost ephemeral" in content

    def test_scripts_are_executable(self) -> None:
        """Should make interceptor scripts executable."""
        with HijackManager() as hijack:
            for cmd in DISTROBOX_COMMANDS:
                script = hijack._hijack_dir / f"distrobox-{cmd}"
                mode = script.stat().st_mode
                assert mode & stat.S_IXUSR, f"distrobox-{cmd} should be user executable"
                assert mode & stat.S_IXGRP, f"distrobox-{cmd} should be group executable"
                assert mode & stat.S_IXOTH, f"distrobox-{cmd} should be other executable"

            router = hijack._hijack_dir / "distrobox"
            mode = router.stat().st_mode
            assert mode & stat.S_IXUSR, "distrobox should be user executable"

    def test_cleanup_on_exit(self) -> None:
        """Should clean up temporary directory on exit."""
        with HijackManager() as hijack:
            tmpdir_path = hijack._hijack_dir
            assert tmpdir_path.exists()

        # After exiting context
        assert not tmpdir_path.exists()

    def test_cleanup_on_exception(self) -> None:
        """Should clean up temporary directory even when exception occurs."""
        tmpdir_path = None
        try:
            with HijackManager() as hijack:
                tmpdir_path = hijack._hijack_dir
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert tmpdir_path is not None
        assert not tmpdir_path.exists()

    def test_hijack_dir_is_none_after_exit(self) -> None:
        """Should set internal state to None after exit."""
        manager = HijackManager()
        with manager:
            pass

        assert manager._tmpdir is None
        assert manager._hijack_dir is None

    def test_distrobox_path_property(self) -> None:
        """Should return correct path for distrobox."""
        with HijackManager() as hijack:
            expected = hijack._hijack_dir / "distrobox"
            assert hijack.distrobox_path == expected

    def test_env_property(self) -> None:
        """Should return environment with hijack directory in PATH."""
        with HijackManager() as hijack:
            env = hijack.env
            assert str(hijack._hijack_dir) in env["PATH"]
            # Hijack dir should be first in PATH
            assert env["PATH"].startswith(str(hijack._hijack_dir))


class TestDistroboxRouterScript:
    """Tests for distrobox router script content."""

    def test_router_intercepts_all_commands(self) -> None:
        """Should intercept all known subcommands."""
        with HijackManager() as hijack:
            router = hijack._hijack_dir / "distrobox"
            content = router.read_text()
            for cmd in DISTROBOX_COMMANDS:
                assert f'exec distrobox-boost {cmd} "$@"' in content

    def test_router_has_fallback_for_unknown(self) -> None:
        """Should have fallback for unknown commands."""
        with HijackManager() as hijack:
            router = hijack._hijack_dir / "distrobox"
            content = router.read_text()
            # Check for fallback case
            assert "*)" in content
            assert "REAL_DISTROBOX" in content


class TestInterceptorScript:
    """Tests for interceptor script content."""

    def test_intercept_script_routes_to_boost(self) -> None:
        """Should route intercepted command to distrobox-boost."""
        with HijackManager() as hijack:
            interceptor = hijack._hijack_dir / "distrobox-create"
            content = interceptor.read_text()
            assert content.startswith("#!/bin/sh\n")
            assert 'exec distrobox-boost create "$@"' in content

    def test_all_interceptors_use_exec(self) -> None:
        """All interceptors should use exec to replace process."""
        with HijackManager() as hijack:
            for cmd in DISTROBOX_COMMANDS:
                interceptor = hijack._hijack_dir / f"distrobox-{cmd}"
                content = interceptor.read_text()
                assert "exec distrobox-boost" in content
