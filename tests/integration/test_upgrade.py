"""Tests for distrobox-upgrade command."""

from __future__ import annotations

import pytest

from distrobox_plus.commands.upgrade import (
    _build_extra_flags,
    create_parser,
)
from distrobox_plus.config import Config

pytestmark = [pytest.mark.integration, pytest.mark.upgrade]


class TestUpgradeHelp:
    """Test upgrade help output."""

    @pytest.mark.fast
    def test_upgrade_help(self, distrobox):
        """Test upgrade --help output."""
        result = distrobox.run("upgrade", ["--help"])

        # Help should show usage and exit 0
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "upgrade" in result.stdout

    @pytest.mark.fast
    def test_upgrade_version(self, distrobox):
        """Test upgrade --version output."""
        result = distrobox.run("upgrade", ["--version"])

        assert "distrobox:" in result.stdout or "distrobox:" in result.stderr


class TestUpgradeParser:
    """Test upgrade argument parsing."""

    @pytest.mark.fast
    def test_parser_all_flag(self):
        """Test parsing -a/--all flag."""
        parser = create_parser()

        parsed = parser.parse_args(["--all"])
        assert parsed.all is True

        parsed = parser.parse_args(["-a"])
        assert parsed.all is True

    @pytest.mark.fast
    def test_parser_running_flag(self):
        """Test parsing --running flag."""
        parser = create_parser()
        parsed = parser.parse_args(["--running", "--all"])

        assert parsed.running is True

    @pytest.mark.fast
    def test_parser_root_flag(self):
        """Test parsing -r/--root flag."""
        parser = create_parser()

        parsed = parser.parse_args(["--root", "--all"])
        assert parsed.root is True

        parsed = parser.parse_args(["-r", "--all"])
        assert parsed.root is True

    @pytest.mark.fast
    def test_parser_verbose_flag(self):
        """Test parsing -v/--verbose flag."""
        parser = create_parser()

        parsed = parser.parse_args(["--verbose", "--all"])
        assert parsed.verbose is True

        parsed = parser.parse_args(["-v", "--all"])
        assert parsed.verbose is True

    @pytest.mark.fast
    def test_parser_containers_positional(self):
        """Test parsing positional container names."""
        parser = create_parser()
        parsed = parser.parse_args(["container1", "container2"])

        assert parsed.containers == ["container1", "container2"]


class TestBuildExtraFlags:
    """Test building extra flags from config."""

    @pytest.mark.fast
    def test_build_extra_flags_empty(self):
        """Test building extra flags with no options."""
        config = Config()
        config.verbose = False
        config.rootful = False

        flags = _build_extra_flags(config)

        assert flags == []

    @pytest.mark.fast
    def test_build_extra_flags_verbose(self):
        """Test building extra flags with verbose."""
        config = Config()
        config.verbose = True
        config.rootful = False

        flags = _build_extra_flags(config)

        assert "--verbose" in flags

    @pytest.mark.fast
    def test_build_extra_flags_rootful(self):
        """Test building extra flags with rootful."""
        config = Config()
        config.verbose = False
        config.rootful = True

        flags = _build_extra_flags(config)

        assert "--root" in flags

    @pytest.mark.fast
    def test_build_extra_flags_both(self):
        """Test building extra flags with both options."""
        config = Config()
        config.verbose = True
        config.rootful = True

        flags = _build_extra_flags(config)

        assert "--verbose" in flags
        assert "--root" in flags


class TestUpgradeNoArgs:
    """Test upgrade command with no arguments."""

    @pytest.mark.fast
    def test_upgrade_no_args_shows_help(self, distrobox):
        """Test that no arguments shows help and exits 0."""
        result = distrobox.run("upgrade", [])

        # Should show help (contains usage info)
        assert "usage:" in result.stdout.lower() or "upgrade" in result.stdout.lower() or "upgrade" in result.stderr.lower()
        # Should exit 0
        assert result.returncode == 0


class TestUpgradeAllEmpty:
    """Test upgrade --all with no containers."""

    @pytest.mark.fast
    def test_upgrade_all_no_containers(self, distrobox):
        """Test --all with no containers exits 0."""
        # This test assumes no distrobox containers exist or will succeed if they do
        # The upgrade command should exit 0 when --all is used but no containers found
        result = distrobox.run("upgrade", ["--all"])

        # Should exit 0 (nothing to upgrade is not an error)
        assert result.returncode == 0
