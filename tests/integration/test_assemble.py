"""Tests for distrobox-assemble command."""

from __future__ import annotations

import base64

import pytest

from distrobox_plus.commands.assemble import (
    ContainerSpec,
    ManifestParser,
    _build_create_args,
    _decode_hooks,
    _encode_variable,
    _sanitize_variable,
    create_parser,
)

pytestmark = [pytest.mark.integration, pytest.mark.assemble]


class TestAssembleHelp:
    """Test assemble help output."""

    @pytest.mark.fast
    def test_assemble_help(self, distrobox):
        """Test assemble --help output."""
        result = distrobox.run("assemble", ["--help"])

        # Help should contain version and key options
        assert "distrobox version:" in result.stdout or "distrobox version:" in result.stderr
        assert "--file" in result.stdout or "--file" in result.stderr
        assert "--replace" in result.stdout or "--replace" in result.stderr

    @pytest.mark.fast
    def test_assemble_version(self, distrobox):
        """Test assemble --version output."""
        result = distrobox.run("assemble", ["--version"])

        assert "distrobox:" in result.stdout or "distrobox:" in result.stderr


class TestAssembleParser:
    """Test assemble argument parsing."""

    @pytest.mark.fast
    def test_parser_create_action(self):
        """Test parsing create action."""
        parser = create_parser()
        parsed = parser.parse_args(["create"])

        assert parsed.action == "create"

    @pytest.mark.fast
    def test_parser_rm_action(self):
        """Test parsing rm action."""
        parser = create_parser()
        parsed = parser.parse_args(["rm"])

        assert parsed.action == "rm"

    @pytest.mark.fast
    def test_parser_file_option(self):
        """Test parsing --file option."""
        parser = create_parser()
        parsed = parser.parse_args(["create", "--file", "/path/to/file.ini"])

        assert parsed.file == "/path/to/file.ini"

    @pytest.mark.fast
    def test_parser_name_option(self):
        """Test parsing -n/--name option."""
        parser = create_parser()

        parsed = parser.parse_args(["create", "--name", "my-box"])
        assert parsed.name == "my-box"

        parsed = parser.parse_args(["create", "-n", "my-box"])
        assert parsed.name == "my-box"

    @pytest.mark.fast
    def test_parser_replace_flag(self):
        """Test parsing -R/--replace flag."""
        parser = create_parser()

        parsed = parser.parse_args(["create", "--replace"])
        assert parsed.replace is True

        parsed = parser.parse_args(["create", "-R"])
        assert parsed.replace is True

    @pytest.mark.fast
    def test_parser_dry_run_flag(self):
        """Test parsing -d/--dry-run flag."""
        parser = create_parser()

        parsed = parser.parse_args(["create", "--dry-run"])
        assert parsed.dry_run is True

        parsed = parser.parse_args(["create", "-d"])
        assert parsed.dry_run is True

    @pytest.mark.fast
    def test_parser_verbose_flag(self):
        """Test parsing -v/--verbose flag."""
        parser = create_parser()

        parsed = parser.parse_args(["create", "--verbose"])
        assert parsed.verbose is True

        parsed = parser.parse_args(["create", "-v"])
        assert parsed.verbose is True


class TestManifestParser:
    """Test manifest parsing."""

    @pytest.mark.fast
    def test_parse_simple_section(self):
        """Test parsing a simple manifest section."""
        content = """\
[my-box]
image=alpine:latest
init=false
"""
        parser = ManifestParser(content)
        specs = parser.parse()

        assert "my-box" in specs
        assert specs["my-box"].name == "my-box"
        assert specs["my-box"].image == "alpine:latest"
        assert specs["my-box"].init is False

    @pytest.mark.fast
    def test_parse_boolean_normalization(self):
        """Test that true/false are normalized to 1/0."""
        content = """\
[box1]
image=alpine
init=true
nvidia=false
"""
        parser = ManifestParser(content)
        specs = parser.parse()

        assert specs["box1"].init is True
        assert specs["box1"].nvidia is False

    @pytest.mark.fast
    def test_parse_multi_value_keys(self):
        """Test accumulation of multi-value keys."""
        content = """\
[box1]
image=alpine
volume=/home:/home
volume=/tmp:/tmp
additional_packages=git
additional_packages=vim
"""
        parser = ManifestParser(content)
        specs = parser.parse()

        assert len(specs["box1"].volumes) == 2
        assert "/home:/home" in specs["box1"].volumes
        assert "/tmp:/tmp" in specs["box1"].volumes
        assert len(specs["box1"].additional_packages) == 2
        assert "git" in specs["box1"].additional_packages
        assert "vim" in specs["box1"].additional_packages

    @pytest.mark.fast
    def test_parse_comments(self):
        """Test that comments are properly stripped."""
        content = """\
# This is a header comment
[my-box]  # inline comment
image=alpine:latest  # trailing comment
# init=true
"""
        parser = ManifestParser(content)
        specs = parser.parse()

        assert "my-box" in specs
        assert specs["my-box"].image == "alpine:latest"
        assert specs["my-box"].init is False  # default, not from commented line

    @pytest.mark.fast
    def test_parse_multiple_sections(self):
        """Test parsing multiple sections."""
        content = """\
[box1]
image=alpine:latest

[box2]
image=fedora:latest
"""
        parser = ManifestParser(content)
        specs = parser.parse()

        assert len(specs) == 2
        assert specs["box1"].image == "alpine:latest"
        assert specs["box2"].image == "fedora:latest"


class TestIncludeResolution:
    """Test include directive resolution."""

    @pytest.mark.fast
    def test_simple_include(self):
        """Test simple include inheritance."""
        content = """\
[base]
image=alpine:latest
init=true

[derived]
include=base
nvidia=true
"""
        parser = ManifestParser(content)
        specs = parser.parse()

        # derived should inherit from base
        assert specs["derived"].image == "alpine:latest"
        assert specs["derived"].init is True
        assert specs["derived"].nvidia is True

    @pytest.mark.fast
    def test_include_override(self):
        """Test that derived values override base values."""
        content = """\
[base]
image=alpine:latest

[derived]
include=base
image=fedora:latest
"""
        parser = ManifestParser(content)
        specs = parser.parse()

        # derived should override image
        assert specs["derived"].image == "fedora:latest"

    @pytest.mark.fast
    def test_include_accumulation(self):
        """Test that multi-value keys accumulate through includes."""
        content = """\
[base]
image=alpine
volume=/base:/base

[derived]
include=base
volume=/derived:/derived
"""
        parser = ManifestParser(content)
        specs = parser.parse()

        # volumes should accumulate
        assert len(specs["derived"].volumes) == 2
        assert "/base:/base" in specs["derived"].volumes
        assert "/derived:/derived" in specs["derived"].volumes

    @pytest.mark.fast
    def test_circular_include_detection(self):
        """Test that circular includes are detected."""
        content = """\
[box1]
include=box2

[box2]
include=box1
"""
        parser = ManifestParser(content)

        with pytest.raises(ValueError) as exc_info:
            parser.parse()

        assert "circular reference" in str(exc_info.value).lower()

    @pytest.mark.fast
    def test_missing_include_detection(self):
        """Test that missing include targets are detected."""
        content = """\
[box1]
include=nonexistent
"""
        parser = ManifestParser(content)

        with pytest.raises(ValueError) as exc_info:
            parser.parse()

        assert "cannot include" in str(exc_info.value).lower()
        assert "nonexistent" in str(exc_info.value)


class TestEncodeVariable:
    """Test _encode_variable function."""

    @pytest.mark.fast
    def test_encode_simple_string(self):
        """Test encoding a simple string."""
        result = _encode_variable("echo hello")
        decoded = base64.b64decode(result).decode()
        assert decoded == "echo hello"

    @pytest.mark.fast
    def test_encode_strips_double_quotes(self):
        """Test that surrounding double quotes are stripped."""
        result = _encode_variable('"echo hello"')
        decoded = base64.b64decode(result).decode()
        assert decoded == "echo hello"

    @pytest.mark.fast
    def test_encode_strips_single_quotes(self):
        """Test that surrounding single quotes are stripped."""
        result = _encode_variable("'echo hello'")
        decoded = base64.b64decode(result).decode()
        assert decoded == "echo hello"


class TestSanitizeVariable:
    """Test _sanitize_variable function."""

    @pytest.mark.fast
    def test_sanitize_no_spaces(self):
        """Test that values without spaces are unchanged."""
        result = _sanitize_variable("value")
        assert result == "value"

    @pytest.mark.fast
    def test_sanitize_with_spaces_adds_quotes(self):
        """Test that spaces cause quotes to be added."""
        result = _sanitize_variable("value with spaces")
        assert result == '"value with spaces"'

    @pytest.mark.fast
    def test_sanitize_with_double_quotes_uses_single(self):
        """Test that double quotes cause single quotes to be used."""
        result = _sanitize_variable('value with "quotes"')
        assert result == "'value with \"quotes\"'"

    @pytest.mark.fast
    def test_sanitize_already_quoted(self):
        """Test that already quoted values are unchanged."""
        result = _sanitize_variable('"already quoted"')
        assert result == '"already quoted"'


class TestDecodeHooks:
    """Test _decode_hooks function."""

    @pytest.mark.fast
    def test_decode_empty_list(self):
        """Test decoding empty list returns empty string."""
        result = _decode_hooks([])
        assert result == ""

    @pytest.mark.fast
    def test_decode_single_hook(self):
        """Test decoding a single hook."""
        encoded = base64.b64encode(b"echo hello").decode()
        result = _decode_hooks([encoded])

        assert "echo hello" in result
        assert result.startswith(": ;")

    @pytest.mark.fast
    def test_decode_multiple_hooks_with_separator(self):
        """Test that multiple hooks are joined with &&."""
        hook1 = base64.b64encode(b"echo hello").decode()
        hook2 = base64.b64encode(b"echo world").decode()
        result = _decode_hooks([hook1, hook2])

        assert "echo hello" in result
        assert "echo world" in result
        assert "&&" in result

    @pytest.mark.fast
    def test_decode_hook_ending_with_semicolon(self):
        """Test that hooks ending with ; don't add &&."""
        hook1 = base64.b64encode(b"echo hello;").decode()
        hook2 = base64.b64encode(b"echo world").decode()
        result = _decode_hooks([hook1, hook2])

        # Should not have && after the semicolon
        # The result should be something like ": ; echo hello;  echo world"
        assert "echo hello;" in result
        assert "echo world" in result


class TestBuildCreateArgs:
    """Test _build_create_args function."""

    @pytest.mark.fast
    def test_build_basic_args(self):
        """Test building basic create arguments."""
        spec = ContainerSpec(
            name="test-box",
            image="alpine:latest",
        )
        args = _build_create_args(spec, verbose=False)

        assert "--yes" in args
        assert "--name" in args
        assert "test-box" in args
        assert "--image" in args
        assert "alpine:latest" in args

    @pytest.mark.fast
    def test_build_with_verbose(self):
        """Test building args with verbose flag."""
        spec = ContainerSpec(name="test", image="alpine")
        args = _build_create_args(spec, verbose=True)

        assert "-v" in args

    @pytest.mark.fast
    def test_build_with_init(self):
        """Test building args with init flag."""
        spec = ContainerSpec(name="test", image="alpine", init=True)
        args = _build_create_args(spec, verbose=False)

        assert "--init" in args

    @pytest.mark.fast
    def test_build_with_no_entry(self):
        """Test building args with entry=false (--no-entry)."""
        spec = ContainerSpec(name="test", image="alpine", entry=False)
        args = _build_create_args(spec, verbose=False)

        assert "--no-entry" in args

    @pytest.mark.fast
    def test_build_with_unshare_flags(self):
        """Test building args with unshare flags."""
        spec = ContainerSpec(
            name="test",
            image="alpine",
            unshare_netns=True,
            unshare_ipc=True,
        )
        args = _build_create_args(spec, verbose=False)

        assert "--unshare-netns" in args
        assert "--unshare-ipc" in args

    @pytest.mark.fast
    def test_build_with_volumes(self):
        """Test building args with volumes."""
        spec = ContainerSpec(
            name="test",
            image="alpine",
            volumes=["/home:/home", "/tmp:/tmp"],
        )
        args = _build_create_args(spec, verbose=False)

        # Each volume should have its own --volume flag
        assert args.count("--volume") == 2
        assert "/home:/home" in args
        assert "/tmp:/tmp" in args

    @pytest.mark.fast
    def test_build_with_additional_packages(self):
        """Test building args with additional packages."""
        spec = ContainerSpec(
            name="test",
            image="alpine",
            additional_packages=["git", "vim", "curl"],
        )
        args = _build_create_args(spec, verbose=False)

        # Packages should be joined into a single string
        assert "--additional-packages" in args
        idx = args.index("--additional-packages")
        assert "git vim curl" == args[idx + 1]


class TestAssembleNoArgs:
    """Test assemble command with no arguments."""

    @pytest.mark.fast
    def test_assemble_no_action_shows_help(self, distrobox):
        """Test that no action shows help and exits with error."""
        result = distrobox.run("assemble", [])

        # Should show error message
        assert "Please specify create or rm" in result.stderr
        # Should exit with error
        assert result.returncode == 1


class TestAssembleDryRun:
    """Test assemble --dry-run functionality."""

    @pytest.mark.fast
    def test_assemble_dry_run(self, distrobox, tmp_path):
        """Test dry-run prints commands without executing."""
        # Create a test manifest
        manifest = tmp_path / "test.ini"
        manifest.write_text("""\
[test-box]
image=alpine:latest
init=false
""")

        result = distrobox.run("assemble", [
            "create",
            "--dry-run",
            "--file", str(manifest),
        ])

        # Should print the create command
        assert "distrobox-create" in result.stdout
        assert "--name" in result.stdout
        assert "test-box" in result.stdout
        assert "--image" in result.stdout
        assert "alpine:latest" in result.stdout

        # Should exit successfully
        assert result.returncode == 0


class TestAssembleMissingFile:
    """Test assemble with missing file."""

    @pytest.mark.fast
    def test_assemble_missing_file(self, distrobox):
        """Test that missing file returns error."""
        result = distrobox.run("assemble", [
            "create",
            "--file", "/nonexistent/path/to/file.ini",
        ])

        assert "does not exist" in result.stderr
        assert result.returncode == 1
