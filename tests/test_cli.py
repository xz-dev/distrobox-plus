"""Tests for CLI (__main__.py)."""

from unittest.mock import patch

import pytest

from distrobox_boost.__main__ import main


class TestCLI:
    """Tests for CLI main function."""

    def test_no_command_shows_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should show help when no command is provided."""
        with patch("sys.argv", ["distrobox-boost"]):
            result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out

    def test_help_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should show help with --help flag."""
        with patch("sys.argv", ["distrobox-boost", "--help"]):
            result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out
        assert "assemble" in captured.out
