"""Tests for CLI (__main__.py)."""

from unittest.mock import MagicMock, patch

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
        assert "usage:" in captured.out

    def test_help_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should show help with --help flag."""
        with patch("sys.argv", ["distrobox-boost", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out
        assert "image" in captured.out

    @patch("distrobox_boost.command.image.run")
    def test_image_command_calls_run(self, mock_run: MagicMock) -> None:
        """Should call image.run with correct arguments."""
        mock_run.return_value = 0
        with patch("sys.argv", ["distrobox-boost", "image", "my-image", "--base", "fedora:latest"]):
            result = main()
        mock_run.assert_called_once_with("my-image", "fedora:latest")
        assert result == 0

    @patch("distrobox_boost.command.image.run")
    def test_image_command_returns_run_exit_code(self, mock_run: MagicMock) -> None:
        """Should return exit code from image.run."""
        mock_run.return_value = 42
        with patch("sys.argv", ["distrobox-boost", "image", "my-image", "--base", "fedora:latest"]):
            result = main()
        assert result == 42

    def test_image_command_requires_base(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should error when --base is not provided."""
        with patch("sys.argv", ["distrobox-boost", "image", "my-image"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "--base" in captured.err

    def test_image_command_requires_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should error when name is not provided."""
        with patch("sys.argv", ["distrobox-boost", "image", "--base", "fedora:latest"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0
