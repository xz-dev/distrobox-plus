"""Tests for command/create.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distrobox_boost.command.create import (
    BAKED_FLAGS,
    extract_arg_value,
    get_boost_image,
    has_boost_image,
    remove_args,
    replace_arg_value,
    run_create,
)


class TestExtractArgValue:
    """Tests for extract_arg_value function."""

    def test_extract_flag_value_format(self) -> None:
        """Should extract value in '--flag value' format."""
        args = ["--name", "mycontainer", "--image", "alpine"]
        result = extract_arg_value(args, ["--name", "-n"])
        assert result == "mycontainer"

    def test_extract_equals_format(self) -> None:
        """Should extract value in '--flag=value' format."""
        args = ["--name=mycontainer", "--image=alpine"]
        result = extract_arg_value(args, ["--name", "-n"])
        assert result == "mycontainer"

    def test_extract_short_flag(self) -> None:
        """Should extract value using short flag."""
        args = ["-n", "mycontainer", "-i", "alpine"]
        result = extract_arg_value(args, ["--name", "-n"])
        assert result == "mycontainer"

    def test_extract_short_flag_equals(self) -> None:
        """Should extract value using short flag with equals."""
        args = ["-n=mycontainer", "-i=alpine"]
        result = extract_arg_value(args, ["--name", "-n"])
        assert result == "mycontainer"

    def test_extract_missing_flag(self) -> None:
        """Should return None when flag is not present."""
        args = ["--image", "alpine"]
        result = extract_arg_value(args, ["--name", "-n"])
        assert result is None

    def test_extract_flag_at_end_without_value(self) -> None:
        """Should return None when flag is at end without value."""
        args = ["--image", "alpine", "--name"]
        result = extract_arg_value(args, ["--name", "-n"])
        assert result is None

    def test_extract_with_multiple_flags(self) -> None:
        """Should extract first matching flag value."""
        args = ["--name", "first", "-n", "second"]
        result = extract_arg_value(args, ["--name", "-n"])
        assert result == "first"

    def test_extract_equals_with_equals_in_value(self) -> None:
        """Should handle values containing equals sign."""
        args = ["--env=FOO=bar"]
        result = extract_arg_value(args, ["--env"])
        assert result == "FOO=bar"


class TestReplaceArgValue:
    """Tests for replace_arg_value function."""

    def test_replace_flag_value_format(self) -> None:
        """Should replace value in '--flag value' format."""
        args = ["--name", "old", "--image", "alpine"]
        result = replace_arg_value(args, ["--name", "-n"], "new")
        assert result == ["--name", "new", "--image", "alpine"]

    def test_replace_equals_format(self) -> None:
        """Should replace value in '--flag=value' format."""
        args = ["--name=old", "--image=alpine"]
        result = replace_arg_value(args, ["--name", "-n"], "new")
        assert result == ["--name=new", "--image=alpine"]

    def test_replace_short_flag(self) -> None:
        """Should replace value using short flag."""
        args = ["-n", "old", "-i", "alpine"]
        result = replace_arg_value(args, ["--name", "-n"], "new")
        assert result == ["-n", "new", "-i", "alpine"]

    def test_replace_preserves_order(self) -> None:
        """Should preserve argument order."""
        args = ["--before", "val", "--name", "old", "--after", "val2"]
        result = replace_arg_value(args, ["--name", "-n"], "new")
        assert result == ["--before", "val", "--name", "new", "--after", "val2"]

    def test_replace_no_match(self) -> None:
        """Should return unchanged args when flag not found."""
        args = ["--image", "alpine"]
        result = replace_arg_value(args, ["--name", "-n"], "new")
        assert result == ["--image", "alpine"]

    def test_replace_uses_first_matching_flag(self) -> None:
        """Should use the actual flag name that was in the args."""
        args = ["--name", "old"]
        result = replace_arg_value(args, ["--name", "-n"], "new")
        assert result == ["--name", "new"]

        args2 = ["-n", "old"]
        result2 = replace_arg_value(args2, ["--name", "-n"], "new")
        assert result2 == ["-n", "new"]


class TestRemoveArgs:
    """Tests for remove_args function."""

    def test_remove_single_flag(self) -> None:
        """Should remove a single flag and its value."""
        args = ["--name", "test", "--additional-packages", "git", "--image", "alpine"]
        result = remove_args(args, ["--additional-packages", "-ap"])
        assert result == ["--name", "test", "--image", "alpine"]

    def test_remove_multiple_flags(self) -> None:
        """Should remove multiple flags and their values."""
        args = ["--name", "test", "--additional-packages", "git", "--init-hooks", "echo"]
        result = remove_args(args, ["--additional-packages", "-ap", "--init-hooks"])
        assert result == ["--name", "test"]

    def test_remove_equals_format(self) -> None:
        """Should remove flag in '--flag=value' format."""
        args = ["--name=test", "--additional-packages=git", "--image=alpine"]
        result = remove_args(args, ["--additional-packages", "-ap"])
        assert result == ["--name=test", "--image=alpine"]

    def test_remove_short_flag(self) -> None:
        """Should remove short flag and its value."""
        args = ["--name", "test", "-ap", "git", "--image", "alpine"]
        result = remove_args(args, ["--additional-packages", "-ap"])
        assert result == ["--name", "test", "--image", "alpine"]

    def test_remove_preserves_order(self) -> None:
        """Should preserve order of remaining arguments."""
        args = ["--a", "1", "--remove", "x", "--b", "2"]
        result = remove_args(args, ["--remove"])
        assert result == ["--a", "1", "--b", "2"]

    def test_remove_no_match(self) -> None:
        """Should return unchanged args when flag not found."""
        args = ["--name", "test", "--image", "alpine"]
        result = remove_args(args, ["--additional-packages"])
        assert result == ["--name", "test", "--image", "alpine"]

    def test_remove_empty_args(self) -> None:
        """Should handle empty argument list."""
        result = remove_args([], ["--flag"])
        assert result == []


class TestHasBoostImage:
    """Tests for has_boost_image function."""

    def test_returns_true_when_config_exists(self, tmp_path: Path) -> None:
        """Should return True when distrobox.ini exists."""
        config_dir = tmp_path / "mycontainer"
        config_dir.mkdir()
        (config_dir / "distrobox.ini").write_text("[mycontainer]\nimage=test\n")

        with patch(
            "distrobox_boost.command.create.get_container_cache_dir",
            return_value=config_dir,
        ):
            assert has_boost_image("mycontainer") is True

    def test_returns_false_when_config_missing(self, tmp_path: Path) -> None:
        """Should return False when distrobox.ini doesn't exist."""
        config_dir = tmp_path / "mycontainer"
        config_dir.mkdir()

        with patch(
            "distrobox_boost.command.create.get_container_cache_dir",
            return_value=config_dir,
        ):
            assert has_boost_image("mycontainer") is False

    def test_returns_false_when_dir_missing(self, tmp_path: Path) -> None:
        """Should return False when cache directory doesn't exist."""
        with patch(
            "distrobox_boost.command.create.get_container_cache_dir",
            return_value=tmp_path / "nonexistent",
        ):
            assert has_boost_image("mycontainer") is False


class TestGetBoostImage:
    """Tests for get_boost_image function."""

    def test_returns_correct_image_name(self) -> None:
        """Should return image name in format {name}:latest."""
        assert get_boost_image("mycontainer") == "mycontainer:latest"

    def test_handles_special_characters(self) -> None:
        """Should handle container names with special characters."""
        assert get_boost_image("my-container_123") == "my-container_123:latest"


class TestBakedFlags:
    """Tests for BAKED_FLAGS constant."""

    def test_contains_expected_flags(self) -> None:
        """Should contain all flags that are baked into optimized images."""
        assert "--additional-packages" in BAKED_FLAGS
        assert "-ap" in BAKED_FLAGS
        assert "--init-hooks" in BAKED_FLAGS
        assert "--pre-init-hooks" in BAKED_FLAGS


class TestRunCreate:
    """Tests for run_create function."""

    @patch("distrobox_boost.command.create.subprocess.run")
    def test_without_boost_image_passthrough(self, mock_run: MagicMock) -> None:
        """Should pass through to distrobox create when no boost image."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch(
            "distrobox_boost.command.create.has_boost_image",
            return_value=False,
        ):
            result = run_create(["--name", "test", "--image", "alpine"])

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["distrobox", "create", "--name", "test", "--image", "alpine"]
        assert result == 0

    @patch("distrobox_boost.command.create.subprocess.run")
    def test_with_boost_image_replaces_image(self, mock_run: MagicMock) -> None:
        """Should replace image when boost image exists."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch(
            "distrobox_boost.command.create.has_boost_image",
            return_value=True,
        ):
            run_create(["--name", "test", "--image", "alpine"])

        cmd = mock_run.call_args[0][0]
        assert "--image" in cmd
        image_idx = cmd.index("--image")
        assert cmd[image_idx + 1] == "test:latest"

    @patch("distrobox_boost.command.create.subprocess.run")
    def test_with_boost_image_removes_baked_flags(self, mock_run: MagicMock) -> None:
        """Should remove baked flags when boost image exists."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch(
            "distrobox_boost.command.create.has_boost_image",
            return_value=True,
        ):
            run_create([
                "--name", "test",
                "--image", "alpine",
                "--additional-packages", "git",
                "--init-hooks", "echo hello",
            ])

        cmd = mock_run.call_args[0][0]
        assert "--additional-packages" not in cmd
        assert "git" not in cmd
        assert "--init-hooks" not in cmd
        assert "echo hello" not in cmd

    @patch("distrobox_boost.command.create.subprocess.run")
    def test_without_name_flag(self, mock_run: MagicMock) -> None:
        """Should pass through when name flag is missing."""
        mock_run.return_value = MagicMock(returncode=0)

        run_create(["--image", "alpine"])

        cmd = mock_run.call_args[0][0]
        assert cmd == ["distrobox", "create", "--image", "alpine"]

    @patch("distrobox_boost.command.create.subprocess.run")
    def test_returns_subprocess_exit_code(self, mock_run: MagicMock) -> None:
        """Should return the subprocess exit code."""
        mock_run.return_value = MagicMock(returncode=42)

        with patch(
            "distrobox_boost.command.create.has_boost_image",
            return_value=False,
        ):
            result = run_create(["--name", "test", "--image", "alpine"])

        assert result == 42

    @patch("distrobox_boost.command.create.subprocess.run")
    @patch("distrobox_boost.command.create.print")
    def test_prints_message_when_using_boost(
        self, mock_print: MagicMock, mock_run: MagicMock
    ) -> None:
        """Should print informational message when using optimized image."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch(
            "distrobox_boost.command.create.has_boost_image",
            return_value=True,
        ):
            run_create(["--name", "mytest", "--image", "alpine"])

        mock_print.assert_called_once()
        assert "mytest" in mock_print.call_args[0][0]
        assert "optimized" in mock_print.call_args[0][0].lower()
