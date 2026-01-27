"""Tests for command/create.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distrobox_boost.command.create import (
    BAKED_FLAGS,
    create_pre_hook,
    extract_arg_value,
    remove_args,
    replace_arg_value,
    run_create,
)
from distrobox_boost.utils.builder import get_boost_image_name, has_config


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


class TestHasConfig:
    """Tests for has_config function (in builder.py)."""

    def test_returns_true_when_config_exists(self, tmp_path: Path) -> None:
        """Should return True when config file exists."""
        config_dir = tmp_path / "mycontainer"
        config_dir.mkdir()
        (config_dir / "distrobox.ini").write_text("image=test\n")

        with patch(
            "distrobox_boost.utils.builder.get_container_config_file",
            return_value=config_dir / "distrobox.ini",
        ):
            assert has_config("mycontainer") is True

    def test_returns_false_when_config_missing(self, tmp_path: Path) -> None:
        """Should return False when config file doesn't exist."""
        config_dir = tmp_path / "mycontainer"
        config_dir.mkdir()

        with patch(
            "distrobox_boost.utils.builder.get_container_config_file",
            return_value=config_dir / "distrobox.ini",
        ):
            assert has_config("mycontainer") is False


class TestGetBoostImageName:
    """Tests for get_boost_image_name function (in builder.py)."""

    def test_returns_correct_image_name(self) -> None:
        """Should return image name in format {name}:latest."""
        assert get_boost_image_name("mycontainer") == "mycontainer:latest"

    def test_handles_special_characters(self) -> None:
        """Should handle container names with special characters."""
        assert get_boost_image_name("my-container_123") == "my-container_123:latest"


class TestBakedFlags:
    """Tests for BAKED_FLAGS constant."""

    def test_contains_expected_flags(self) -> None:
        """Should contain all flags that are baked into optimized images."""
        assert "--additional-packages" in BAKED_FLAGS
        assert "-ap" in BAKED_FLAGS
        assert "--init-hooks" in BAKED_FLAGS
        assert "--pre-init-hooks" in BAKED_FLAGS


class TestCreatePreHook:
    """Tests for create_pre_hook function."""

    def test_returns_none_without_name(self) -> None:
        """Should return None when no --name flag is present."""
        args = ["--image", "alpine"]
        result = create_pre_hook(args)
        assert result is None

    def test_returns_none_when_no_config(self) -> None:
        """Should return None when no config exists for the container."""
        with patch("distrobox_boost.command.create.has_config", return_value=False):
            args = ["--name", "test", "--image", "alpine"]
            result = create_pre_hook(args)
            assert result is None

    def test_builds_image_when_needed(self) -> None:
        """Should build image when config exists but image doesn't."""
        with (
            patch("distrobox_boost.command.create.has_config", return_value=True),
            patch("distrobox_boost.command.create.needs_rebuild", return_value=True),
            patch("distrobox_boost.command.create.ensure_boost_image", return_value=0) as mock_build,
            patch("distrobox_boost.command.create.get_boost_image_name", return_value="test:latest"),
        ):
            args = ["--name", "test", "--image", "alpine"]
            create_pre_hook(args)
            mock_build.assert_called_once_with("test")

    def test_returns_none_on_build_failure(self) -> None:
        """Should return None when image build fails."""
        with (
            patch("distrobox_boost.command.create.has_config", return_value=True),
            patch("distrobox_boost.command.create.needs_rebuild", return_value=True),
            patch("distrobox_boost.command.create.ensure_boost_image", return_value=1),
        ):
            args = ["--name", "test", "--image", "alpine"]
            result = create_pre_hook(args)
            assert result is None

    def test_replaces_image_and_removes_baked_flags(self) -> None:
        """Should replace image and remove baked flags when config exists."""
        with (
            patch("distrobox_boost.command.create.has_config", return_value=True),
            patch("distrobox_boost.command.create.needs_rebuild", return_value=False),
            patch("distrobox_boost.command.create.get_boost_image_name", return_value="test:latest"),
        ):
            args = [
                "--name", "test",
                "--image", "alpine",
                "--additional-packages", "git",
                "--init-hooks", "echo hello",
            ]
            result = create_pre_hook(args)

            assert result is not None
            # Check image was replaced
            assert "--image" in result
            image_idx = result.index("--image")
            assert result[image_idx + 1] == "test:latest"
            # Check baked flags were removed
            assert "--additional-packages" not in result
            assert "git" not in result
            assert "--init-hooks" not in result
            assert "echo hello" not in result


class TestRunCreate:
    """Tests for run_create function."""

    @patch("distrobox_boost.command.wrapper.subprocess.run")
    @patch("distrobox_boost.command.wrapper.shutil.which")
    @patch("distrobox_boost.command.create.has_config")
    def test_without_boost_config_passthrough(
        self, mock_has_config: MagicMock, mock_which: MagicMock, mock_run: MagicMock
    ) -> None:
        """Should pass through to distrobox create when no config exists."""
        mock_has_config.return_value = False
        mock_which.return_value = "/usr/bin/distrobox-create"
        mock_run.return_value = MagicMock(returncode=0)

        result = run_create(["--name", "test", "--image", "alpine"])

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "/usr/bin/distrobox-create" in cmd
        assert "--name" in cmd
        assert "test" in cmd
        assert "--image" in cmd
        assert "alpine" in cmd
        assert result == 0

    @patch("distrobox_boost.command.wrapper.subprocess.run")
    @patch("distrobox_boost.command.wrapper.shutil.which")
    @patch("distrobox_boost.command.create.get_boost_image_name")
    @patch("distrobox_boost.command.create.needs_rebuild")
    @patch("distrobox_boost.command.create.has_config")
    def test_with_boost_config_replaces_image(
        self,
        mock_has_config: MagicMock,
        mock_needs_rebuild: MagicMock,
        mock_get_image: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Should replace image when config exists."""
        mock_has_config.return_value = True
        mock_needs_rebuild.return_value = False
        mock_get_image.return_value = "test:latest"
        mock_which.return_value = "/usr/bin/distrobox-create"
        mock_run.return_value = MagicMock(returncode=0)

        run_create(["--name", "test", "--image", "alpine"])

        cmd = mock_run.call_args[0][0]
        # Check that the boost image is used
        assert "test:latest" in cmd

    @patch("distrobox_boost.command.wrapper.subprocess.run")
    @patch("distrobox_boost.command.wrapper.shutil.which")
    @patch("distrobox_boost.command.create.get_boost_image_name")
    @patch("distrobox_boost.command.create.needs_rebuild")
    @patch("distrobox_boost.command.create.has_config")
    def test_with_boost_config_removes_baked_flags(
        self,
        mock_has_config: MagicMock,
        mock_needs_rebuild: MagicMock,
        mock_get_image: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Should remove baked flags when config exists."""
        mock_has_config.return_value = True
        mock_needs_rebuild.return_value = False
        mock_get_image.return_value = "test:latest"
        mock_which.return_value = "/usr/bin/distrobox-create"
        mock_run.return_value = MagicMock(returncode=0)

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

    @patch("distrobox_boost.command.wrapper.subprocess.run")
    @patch("distrobox_boost.command.wrapper.shutil.which")
    def test_without_name_flag(
        self, mock_which: MagicMock, mock_run: MagicMock
    ) -> None:
        """Should pass through when name flag is missing."""
        mock_which.return_value = "/usr/bin/distrobox-create"
        mock_run.return_value = MagicMock(returncode=0)

        run_create(["--image", "alpine"])

        cmd = mock_run.call_args[0][0]
        assert "--image" in cmd
        assert "alpine" in cmd

    @patch("distrobox_boost.command.wrapper.subprocess.run")
    @patch("distrobox_boost.command.wrapper.shutil.which")
    @patch("distrobox_boost.command.create.has_config")
    def test_returns_subprocess_exit_code(
        self, mock_has_config: MagicMock, mock_which: MagicMock, mock_run: MagicMock
    ) -> None:
        """Should return the subprocess exit code."""
        mock_has_config.return_value = False
        mock_which.return_value = "/usr/bin/distrobox-create"
        mock_run.return_value = MagicMock(returncode=42)

        result = run_create(["--name", "test", "--image", "alpine"])

        assert result == 42
