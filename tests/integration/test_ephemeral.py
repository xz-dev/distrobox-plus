"""Tests for distrobox-ephemeral command."""

from __future__ import annotations

import re

import pytest

from distrobox_plus.commands.ephemeral import (
    EphemeralOptions,
    _build_create_args,
    _build_enter_args,
    _build_ephemeral_options,
    _build_extra_flags,
    _build_rm_args,
    _split_args,
    create_parser,
    generate_ephemeral_name,
)
from distrobox_plus.config import Config

pytestmark = [pytest.mark.integration, pytest.mark.ephemeral]


class TestEphemeralNameGeneration:
    """Test ephemeral name generation."""

    @pytest.mark.fast
    def test_generate_ephemeral_name_format(self):
        """Test that generated names match expected format."""
        name = generate_ephemeral_name()

        # Should match distrobox-XXXXXXXXXX pattern (mktemp uses [A-Za-z0-9])
        assert re.match(r"^distrobox-[A-Za-z0-9]{10}$", name)

    @pytest.mark.fast
    def test_generate_ephemeral_name_unique(self):
        """Test that generated names are unique."""
        names = [generate_ephemeral_name() for _ in range(100)]

        # All names should be unique
        assert len(set(names)) == len(names)


class TestEphemeralHelp:
    """Test ephemeral help output."""

    @pytest.mark.fast
    def test_ephemeral_help(self, distrobox):
        """Test ephemeral --help output."""
        result = distrobox.run("ephemeral", ["--help"])

        # Help should contain key information
        assert "distrobox version:" in result.stdout or "distrobox version:" in result.stderr
        assert "--root" in result.stdout or "--root" in result.stderr

    @pytest.mark.fast
    def test_ephemeral_version(self, distrobox):
        """Test ephemeral --version output."""
        result = distrobox.run("ephemeral", ["--version"])

        assert "distrobox:" in result.stdout or "distrobox:" in result.stderr


class TestEphemeralParser:
    """Test ephemeral argument parsing."""

    @pytest.mark.fast
    def test_parser_name_flag(self):
        """Test parsing --name flag."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args(["--name", "my-ephemeral"])

        assert parsed.name == "my-ephemeral"

    @pytest.mark.fast
    def test_parser_root_flag(self):
        """Test parsing --root flag."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args(["--root"])

        assert parsed.root is True

    @pytest.mark.fast
    def test_parser_verbose_flag(self):
        """Test parsing --verbose flag."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args(["--verbose"])

        assert parsed.verbose is True

    @pytest.mark.fast
    def test_parser_exec_flag(self):
        """Test parsing --exec/-e flag."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args(["-e"])

        assert parsed.exec_delimiter is True

    @pytest.mark.fast
    def test_parser_additional_flags(self):
        """Test parsing --additional-flags."""
        parser = create_parser()
        # Note: value must not start with -- or it's treated as a flag
        parsed, _ = parser.parse_known_args(["--additional-flags", "cap-add=SYS_ADMIN"])

        assert "cap-add=SYS_ADMIN" in parsed.additional_flags

    @pytest.mark.fast
    def test_parser_additional_packages(self):
        """Test parsing --additional-packages."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args(["--additional-packages", "vim"])

        assert "vim" in parsed.additional_packages

    @pytest.mark.fast
    def test_parser_init_hooks(self):
        """Test parsing --init-hooks."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args(["--init-hooks", "echo hello"])

        assert parsed.init_hooks == "echo hello"

    @pytest.mark.fast
    def test_parser_pre_init_hooks(self):
        """Test parsing --pre-init-hooks."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args(["--pre-init-hooks", "echo pre"])

        assert parsed.pre_init_hooks == "echo pre"


class TestEphemeralSplitArgs:
    """Test argument splitting."""

    @pytest.mark.fast
    def test_split_args_with_double_dash(self):
        """Test splitting args at --."""
        ephemeral_args, container_cmd = _split_args(["--name", "test", "--", "echo", "hello"])

        assert ephemeral_args == ["--name", "test"]
        assert container_cmd == ["echo", "hello"]

    @pytest.mark.fast
    def test_split_args_with_e_flag(self):
        """Test splitting args at -e."""
        ephemeral_args, container_cmd = _split_args(["--root", "-e", "bash"])

        assert ephemeral_args == ["--root"]
        assert container_cmd == ["bash"]

    @pytest.mark.fast
    def test_split_args_with_exec_flag(self):
        """Test splitting args at --exec."""
        ephemeral_args, container_cmd = _split_args(["--verbose", "--exec", "zsh"])

        assert ephemeral_args == ["--verbose"]
        assert container_cmd == ["zsh"]

    @pytest.mark.fast
    def test_split_args_no_delimiter(self):
        """Test splitting args without delimiter."""
        ephemeral_args, container_cmd = _split_args(["--name", "test", "--root"])

        assert ephemeral_args == ["--name", "test", "--root"]
        assert container_cmd == []

    @pytest.mark.fast
    def test_split_args_empty(self):
        """Test splitting empty args."""
        ephemeral_args, container_cmd = _split_args([])

        assert ephemeral_args == []
        assert container_cmd == []


class TestEphemeralOptions:
    """Test EphemeralOptions dataclass."""

    @pytest.mark.fast
    def test_ephemeral_options_defaults(self):
        """Test EphemeralOptions default values."""
        opts = EphemeralOptions()

        assert opts.name == ""
        assert opts.container_command == []
        assert opts.create_flags == []
        assert opts.additional_flags == []
        assert opts.additional_packages == []
        assert opts.init_hooks == ""
        assert opts.pre_init_hooks == ""

    @pytest.mark.fast
    def test_ephemeral_options_with_values(self):
        """Test EphemeralOptions with values."""
        opts = EphemeralOptions(
            name="my-ephemeral",
            container_command=["bash"],
            create_flags=["--image", "alpine"],
            additional_flags=["--cap-add=SYS_ADMIN"],
            additional_packages=["vim"],
            init_hooks="echo init",
            pre_init_hooks="echo pre",
        )

        assert opts.name == "my-ephemeral"
        assert opts.container_command == ["bash"]
        assert opts.create_flags == ["--image", "alpine"]
        assert opts.additional_flags == ["--cap-add=SYS_ADMIN"]
        assert opts.additional_packages == ["vim"]
        assert opts.init_hooks == "echo init"
        assert opts.pre_init_hooks == "echo pre"


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


class TestBuildCreateArgs:
    """Test building create command arguments."""

    @pytest.mark.fast
    def test_build_create_args_basic(self):
        """Test building basic create args."""
        opts = EphemeralOptions(name="test-ephemeral")
        extra_flags: list[str] = []

        args = _build_create_args(opts, extra_flags)

        assert "--yes" in args
        assert "--name" in args
        assert "test-ephemeral" in args

    @pytest.mark.fast
    def test_build_create_args_with_additional_flags(self):
        """Test building create args with additional flags."""
        opts = EphemeralOptions(
            name="test",
            additional_flags=["--cap-add=SYS_ADMIN", "--privileged"],
        )
        extra_flags: list[str] = []

        args = _build_create_args(opts, extra_flags)

        assert "--additional-flags" in args
        # Flags should be combined
        combined_idx = args.index("--additional-flags") + 1
        assert "--cap-add=SYS_ADMIN" in args[combined_idx]
        assert "--privileged" in args[combined_idx]

    @pytest.mark.fast
    def test_build_create_args_with_additional_packages(self):
        """Test building create args with additional packages."""
        opts = EphemeralOptions(
            name="test",
            additional_packages=["vim", "git"],
        )
        extra_flags: list[str] = []

        args = _build_create_args(opts, extra_flags)

        assert "--additional-packages" in args

    @pytest.mark.fast
    def test_build_create_args_with_init_hooks(self):
        """Test building create args with init hooks."""
        opts = EphemeralOptions(
            name="test",
            init_hooks="echo hello",
        )
        extra_flags: list[str] = []

        args = _build_create_args(opts, extra_flags)

        assert "--init-hooks" in args
        hooks_idx = args.index("--init-hooks") + 1
        assert args[hooks_idx] == "echo hello"

    @pytest.mark.fast
    def test_build_create_args_with_extra_flags(self):
        """Test building create args with extra flags."""
        opts = EphemeralOptions(name="test")
        extra_flags = ["--verbose", "--root"]

        args = _build_create_args(opts, extra_flags)

        assert "--verbose" in args
        assert "--root" in args


class TestBuildEnterArgs:
    """Test building enter command arguments."""

    @pytest.mark.fast
    def test_build_enter_args_basic(self):
        """Test building basic enter args."""
        opts = EphemeralOptions(name="test-ephemeral")
        extra_flags: list[str] = []

        args = _build_enter_args(opts, extra_flags)

        assert "test-ephemeral" in args

    @pytest.mark.fast
    def test_build_enter_args_with_command(self):
        """Test building enter args with command."""
        opts = EphemeralOptions(
            name="test",
            container_command=["echo", "hello"],
        )
        extra_flags: list[str] = []

        args = _build_enter_args(opts, extra_flags)

        assert "--" in args
        assert "echo" in args
        assert "hello" in args

    @pytest.mark.fast
    def test_build_enter_args_with_extra_flags(self):
        """Test building enter args with extra flags."""
        opts = EphemeralOptions(name="test")
        extra_flags = ["--verbose"]

        args = _build_enter_args(opts, extra_flags)

        assert "--verbose" in args


class TestBuildRmArgs:
    """Test building rm command arguments."""

    @pytest.mark.fast
    def test_build_rm_args_basic(self):
        """Test building basic rm args."""
        args = _build_rm_args("test-container", [])

        assert "--force" in args
        assert "test-container" in args
        assert "--yes" in args

    @pytest.mark.fast
    def test_build_rm_args_with_extra_flags(self):
        """Test building rm args with extra flags."""
        args = _build_rm_args("test-container", ["--verbose", "--root"])

        assert "--verbose" in args
        assert "--root" in args
        assert "--force" in args
        assert "test-container" in args


class TestBuildEphemeralOptions:
    """Test building EphemeralOptions from parsed arguments."""

    @pytest.mark.fast
    def test_build_ephemeral_options_with_name(self):
        """Test building options with provided name."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args(["--name", "my-ephemeral"])

        opts = _build_ephemeral_options(parsed, [], ["bash"])

        assert opts.name == "my-ephemeral"
        assert opts.container_command == ["bash"]

    @pytest.mark.fast
    def test_build_ephemeral_options_generates_name(self):
        """Test building options generates name when not provided."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args([])

        opts = _build_ephemeral_options(parsed, [], [])

        assert opts.name.startswith("distrobox-")
        assert len(opts.name) == len("distrobox-") + 10

    @pytest.mark.fast
    def test_build_ephemeral_options_with_create_flags(self):
        """Test building options with create flags."""
        parser = create_parser()
        parsed, _ = parser.parse_known_args([])

        opts = _build_ephemeral_options(parsed, ["--image", "alpine"], [])

        assert opts.create_flags == ["--image", "alpine"]
