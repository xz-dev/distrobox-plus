"""distrobox-assemble command implementation.

Manages multiple distrobox containers via a manifest/INI file.
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

from ..config import VERSION, Config, check_sudo_doas
from ..container import detect_container_manager
from ..utils.console import print_msg, print_error, red


@dataclass
class ContainerSpec:
    """Specification for a single container from manifest."""

    name: str = ""
    image: str = ""
    clone: str = ""
    home: str = ""
    hostname: str = ""
    init: bool = False
    entry: bool = True  # entry=0 means --no-entry
    nvidia: bool = False
    root: bool = False
    pull: bool = False
    start_now: bool = False
    volumes: list[str] = field(default_factory=list)
    additional_packages: list[str] = field(default_factory=list)
    additional_flags: list[str] = field(default_factory=list)
    init_hooks: list[str] = field(default_factory=list)  # base64 encoded
    pre_init_hooks: list[str] = field(default_factory=list)  # base64 encoded
    unshare_groups: bool = False
    unshare_ipc: bool = False
    unshare_netns: bool = False
    unshare_process: bool = False
    unshare_devsys: bool = False
    unshare_all: bool = False
    exported_apps: list[str] = field(default_factory=list)
    exported_bins: list[str] = field(default_factory=list)
    exported_bins_path: str = ""


class ManifestParser:
    """Parse distrobox manifest/INI files."""

    MULTI_VALUE_KEYS = frozenset({
        "volume", "additional_packages", "additional_flags",
        "init_hooks", "pre_init_hooks", "exported_apps", "exported_bins"
    })

    BOOLEAN_KEYS = frozenset({
        "init", "entry", "nvidia", "root", "pull", "start_now",
        "unshare_groups", "unshare_ipc", "unshare_netns",
        "unshare_process", "unshare_devsys", "unshare_all"
    })

    HOOK_KEYS = frozenset({"init_hooks", "pre_init_hooks"})

    def __init__(self, content: str):
        self.content = content

    @classmethod
    def from_file(cls, path: str) -> ManifestParser:
        """Create parser from file path."""
        with open(path) as f:
            return cls(f.read())

    def parse(self) -> dict[str, ContainerSpec]:
        """Parse manifest and resolve includes.

        Returns:
            Dict mapping container names to their specifications.
        """
        # First pass: collect raw sections
        raw_sections = self._parse_raw_sections()

        # Resolve includes
        resolved = self._resolve_includes(raw_sections)

        # Convert to ContainerSpec objects
        return self._build_specs(resolved)

    def _parse_raw_sections(self) -> dict[str, dict[str, list[str]]]:
        """Parse manifest into raw sections with multi-value accumulation."""
        sections: dict[str, dict[str, list[str]]] = {}
        current_section: str | None = None
        current_values: dict[str, list[str]] = {}

        for line in self.content.splitlines():
            # Clean up the line (matches shell script processing)
            # Remove comments and trailing spaces
            # sed 's/\t/ /g' | sed 's/^#.*//g' | sed 's/].*#.*//g' | sed 's/ #.*//g' | sed 's/\s*$//g'
            line = line.replace('\t', ' ')
            line = re.sub(r'^#.*', '', line)
            line = re.sub(r'\].*#.*', '', line)
            line = re.sub(r' #.*', '', line)
            line = line.rstrip()

            if not line:
                continue

            # Detect section header
            if line.startswith('['):
                # Save previous section
                if current_section is not None:
                    sections[current_section] = current_values

                # Start new section
                # Shell uses: tr -d '][ ' which removes ALL brackets and spaces
                # not just leading/trailing ones
                current_section = line.translate(str.maketrans('', '', '[] '))
                current_values = {}
                continue

            # Skip if no section yet
            if current_section is None:
                continue

            # Parse key=value
            if '=' not in line:
                continue

            key, value = line.split('=', 1)
            # Shell uses: tr -d ' ' which removes ALL spaces from key
            key = key.replace(' ', '')
            # Shell: cut -d'=' -f2- does NOT strip value
            # Line trailing spaces already removed by rstrip() above

            # Normalize booleans
            if value == "true":
                value = "1"
            elif value == "false":
                value = "0"

            # Encode hooks in base64
            if key in self.HOOK_KEYS:
                value = _encode_variable(value)
            else:
                value = _sanitize_variable(value)

            # Accumulate multi-value keys
            if key in self.MULTI_VALUE_KEYS:
                if key not in current_values:
                    current_values[key] = []
                current_values[key].append(value)
            elif key == "include":
                # include is also multi-value for inheritance chain
                if key not in current_values:
                    current_values[key] = []
                current_values[key].append(value)
            else:
                current_values[key] = [value]

        # Save last section
        if current_section is not None:
            sections[current_section] = current_values

        return sections

    def _resolve_includes(
        self,
        raw_sections: dict[str, dict[str, list[str]]],
    ) -> dict[str, dict[str, list[str]]]:
        """Resolve include directives with cycle detection.

        Uses accumulated include_stack per section (matching shell behavior).
        Shell clears include_stack at each section start, then accumulates
        all included definitions. This prevents including the same definition
        twice within a section's inheritance chain (including diamond inheritance).
        """
        resolved: dict[str, dict[str, list[str]]] = {}

        def resolve_section(name: str) -> dict[str, list[str]]:
            """Resolve a top-level section (starts with empty include_stack)."""
            result, _ = resolve_includes(name, [])
            return result

        def resolve_includes(
            name: str,
            include_stack: list[str],
        ) -> tuple[dict[str, list[str]], list[str]]:
            """Resolve includes for a section.

            Args:
                name: Section name to resolve
                include_stack: Accumulated list of already-included sections
                              (shell uses string with ¤ separator, we use list)
                              Note: does NOT include the top-level section being resolved

            Returns:
                Tuple of (resolved values dict, updated include_stack)
            """
            # Check for circular/duplicate reference (shell: expr match on stack)
            # Shell checks BEFORE adding to stack
            if name in include_stack:
                # Shell format: newest first, e.g. [c]¤[b]¤[a]
                stack_str = "¤".join(f"[{s}]" for s in include_stack)
                raise ValueError(
                    f"circular reference detected: including [{name}] again after {stack_str}"
                )

            # Check if section exists
            if name not in raw_sections:
                raise ValueError(f"cannot include '{name}': definition not found")

            # Add to include stack AFTER check (shell: include_stack="[${value}]¤${include_stack}")
            include_stack = [name] + include_stack

            raw = raw_sections[name]
            result: dict[str, list[str]] = {}

            # Process includes first
            for include_name in raw.get("include", []):
                # Shell uses: tr -d '"' which removes ALL double quotes
                # (not just leading/trailing, and not single quotes)
                include_name = include_name.replace('"', '')
                base, include_stack = resolve_includes(include_name, include_stack)
                for key, values in base.items():
                    if key == "include":
                        continue
                    if key not in result:
                        result[key] = []
                    result[key].extend(values)

            # Apply own values (override or accumulate)
            for key, values in raw.items():
                if key == "include":
                    continue
                if key in self.MULTI_VALUE_KEYS:
                    if key not in result:
                        result[key] = []
                    result[key].extend(values)
                else:
                    result[key] = list(values)

            return result, include_stack

        # Resolve all sections (each starts with empty include_stack, matching shell)
        for name in raw_sections:
            if name not in resolved:
                resolved[name] = resolve_section(name)

        return resolved

    def _build_specs(
        self,
        resolved: dict[str, dict[str, list[str]]],
    ) -> dict[str, ContainerSpec]:
        """Convert resolved sections to ContainerSpec objects."""
        specs: dict[str, ContainerSpec] = {}

        for name, values in resolved.items():
            spec = ContainerSpec(name=name)

            # Simple string values
            for key in ("image", "clone", "home", "hostname", "exported_bins_path"):
                if key in values and values[key]:
                    val = values[key][-1]  # Take last value
                    val = _strip_quotes(val)
                    setattr(spec, key, val)

            # Boolean values
            for key in self.BOOLEAN_KEYS:
                if key in values and values[key]:
                    val = values[key][-1]
                    setattr(spec, key, val == "1")

            # Multi-value keys
            if "volume" in values:
                spec.volumes = [_strip_quotes(v) for v in values["volume"]]
            if "additional_packages" in values:
                spec.additional_packages = [_strip_quotes(v) for v in values["additional_packages"]]
            if "additional_flags" in values:
                spec.additional_flags = [_strip_quotes(v) for v in values["additional_flags"]]
            if "init_hooks" in values:
                spec.init_hooks = values["init_hooks"]
            if "pre_init_hooks" in values:
                spec.pre_init_hooks = values["pre_init_hooks"]
            if "exported_apps" in values:
                spec.exported_apps = [_strip_quotes(v) for v in values["exported_apps"]]
            if "exported_bins" in values:
                spec.exported_bins = [_strip_quotes(v) for v in values["exported_bins"]]

            specs[name] = spec

        return specs


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for distrobox-assemble."""
    epilog = """\
Usage:

    distrobox assemble create
    distrobox assemble rm
    distrobox assemble create --file /path/to/file.ini
    distrobox assemble rm --file /path/to/file.ini
    distrobox assemble create --replace --file /path/to/file.ini
"""
    parser = argparse.ArgumentParser(
        prog="distrobox-assemble",
        description=f"distrobox version: {VERSION}\n\n"
        "Create and manage distroboxes from manifest files.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=["create", "rm"],
        help="Action to perform: create or rm",
    )
    parser.add_argument(
        "--file",
        help="path or URL to the distrobox manifest/ini file",
    )
    parser.add_argument(
        "-n", "--name",
        help="run against a single entry in the manifest/ini file",
    )
    parser.add_argument(
        "-R", "--replace",
        action="store_true",
        help="replace already existing distroboxes with matching names",
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="only print the container manager command generated",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="show more verbosity",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"distrobox: {VERSION}",
    )
    return parser


def _print_sudo_error() -> int:
    """Print error message when running via sudo/doas."""
    print_error(f"Running {sys.argv[0]} via SUDO/DOAS is not supported.")
    print_error("Instead, please try using root=true property in the distrobox.ini file.")
    return 1


def _download_file(url: str, timeout: int = 3) -> str | None:
    """Download file content from URL.

    Args:
        url: URL to download from
        timeout: Connection timeout in seconds

    Returns:
        File content as string, or None on failure
    """
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (URLError, ValueError):
        # ValueError is raised for invalid URLs (e.g., file paths)
        return None


def _strip_quotes(value: str) -> str:
    """Strip surrounding quotes if they form a matching pair.

    Matches shell quote parsing behavior - only removes quotes
    if they form a complete pair (both start and end with same quote).
    """
    if len(value) >= 2:
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
    return value


def _encode_variable(value: str) -> str:
    """Encode value in base64, stripping surrounding quotes.

    Matches original encode_variable() function.
    """
    # Remove surrounding quotes
    value = _strip_quotes(value)

    return base64.b64encode(value.encode()).decode()


def _sanitize_variable(value: str) -> str:
    """Sanitize value by adding quotes if needed.

    Matches original sanitize_variable() function.
    """
    # If there are spaces but no quotes, add them
    if " " in value and not value.startswith('"') and not value.startswith("'"):
        if '"' in value:
            value = f"'{value}'"
        else:
            value = f'"{value}"'

    return value


def _decode_hooks(encoded_hooks: list[str]) -> str:
    """Decode base64 hooks and join with &&.

    Matches original shell script behavior from lines 391-438.
    """
    if not encoded_hooks:
        return ""

    args = ": ;"
    separator = ""

    for encoded in encoded_hooks:
        if not encoded:
            continue

        try:
            decoded = base64.b64decode(encoded).decode()
        except Exception:
            continue

        args = f"{args} {separator} {decoded}"

        # Add && separator unless line ends with ; or &&
        if not re.search(r';\s*$', decoded) and not re.search(r'&&\s*$', decoded):
            separator = "&&"
        else:
            separator = ""

    return args


def _build_create_args(spec: ContainerSpec, verbose: bool) -> list[str]:
    """Build arguments for distrobox-create.

    Matches original shell script from lines 339-468.
    """
    args = ["--yes"]

    if verbose:
        args.append("-v")
    if spec.name:
        args.extend(["--name", spec.name])
    if spec.image:
        args.extend(["--image", spec.image])
    if spec.clone:
        args.extend(["--clone", spec.clone])
    if spec.init:
        args.append("--init")
    if spec.root:
        args.append("--root")
    if spec.pull:
        args.append("--pull")
    if not spec.entry:  # entry=0 means --no-entry
        args.append("--no-entry")
    if spec.nvidia:
        args.append("--nvidia")

    # Unshare flags
    if spec.unshare_netns:
        args.append("--unshare-netns")
    if spec.unshare_groups:
        args.append("--unshare-groups")
    if spec.unshare_ipc:
        args.append("--unshare-ipc")
    if spec.unshare_process:
        args.append("--unshare-process")
    if spec.unshare_devsys:
        args.append("--unshare-devsys")
    if spec.unshare_all:
        args.append("--unshare-all")

    if spec.home:
        args.extend(["--home", spec.home])
    if spec.hostname:
        args.extend(["--hostname", spec.hostname])

    # Hooks - decode and pass as single string
    if spec.init_hooks:
        decoded = _decode_hooks(spec.init_hooks)
        if decoded:
            args.extend(["--init-hooks", decoded])
    if spec.pre_init_hooks:
        decoded = _decode_hooks(spec.pre_init_hooks)
        if decoded:
            args.extend(["--pre-init-hooks", decoded])

    # Additional packages - join all into single string
    if spec.additional_packages:
        all_packages = " ".join(spec.additional_packages)
        args.extend(["--additional-packages", all_packages])

    # Volumes - each gets own flag
    for vol in spec.volumes:
        args.extend(["--volume", vol])

    # Additional flags - each gets own flag
    for flag in spec.additional_flags:
        args.extend(["--additional-flags", flag])

    return args


def _run_exports(
    name: str,
    root_flag: bool,
    spec: ContainerSpec,
    verbose: bool,
) -> int:
    """Run exports for apps and binaries after container creation.

    Args:
        name: Container name
        root_flag: Whether container is rootful
        spec: Container specification
        verbose: Enable verbose output

    Returns:
        Exit code
    """
    from .enter import run as enter_run

    # Determine export path
    export_path = spec.exported_bins_path
    if not export_path:
        export_path = str(Path.home() / ".local" / "bin")

    root_args = ["--root"] if root_flag else []

    # Export apps
    for apps in spec.exported_apps:
        # Split by spaces (apps can be space-separated)
        for app in apps.split():
            if not app:
                continue
            enter_run([
                *root_args,
                "-n", name,
                "--",
                "distrobox-export", "--app", app,
            ])

    # Export bins
    for bins in spec.exported_bins:
        # Split by spaces (bins can be space-separated)
        for bin_path in bins.split():
            if not bin_path:
                continue
            enter_run([
                *root_args,
                "-n", name,
                "--",
                "distrobox-export", "--bin", bin_path,
                "--export-path", export_path,
            ])

    return 0


def run(args: list[str] | None = None) -> int:
    """Run the distrobox-assemble command.

    Args:
        args: Command line arguments (uses sys.argv if None)

    Returns:
        Exit code
    """
    # Check for sudo/doas
    if check_sudo_doas():
        return _print_sudo_error()

    # Parse arguments
    parser = create_parser()
    if args is None:
        args = sys.argv[1:]
    parsed = parser.parse_args(args)

    # Validate action
    if parsed.action is None:
        print_error("Please specify create or rm.")
        parser.print_help()
        return 1

    delete = (parsed.action == "rm")

    # Load config
    config = Config.load()
    if parsed.verbose:
        config.verbose = True

    # Resolve input file
    input_file = parsed.file or "./distrobox.ini"

    # Load manifest (file or URL)
    if Path(input_file).exists():
        content = Path(input_file).read_text()
    else:
        content = _download_file(input_file)
        if content is None:
            print_error(f"[error]File {input_file} does not exist.[/error]")
            return 1

    # Parse manifest
    try:
        mp = ManifestParser(content)
        specs = mp.parse()
    except ValueError as e:
        print_error(f"[error]ERROR {e}[/error]")
        return 1

    # Filter by name if specified
    if parsed.name:
        if parsed.name not in specs:
            return 0  # Skip silently (matches shell behavior)
        specs = {parsed.name: specs[parsed.name]}

    # Import commands here to avoid circular imports
    from .rm import run as rm_run
    from .create import run as create_run
    from .enter import run as enter_run

    # Process each container
    for name, spec in specs.items():
        spec.name = name

        # Determine root flag
        root_args = ["--root"] if spec.root else []

        # Delete or replace
        if delete or parsed.replace:
            print_msg(f" - Deleting {name}...")

            if not parsed.dry_run:
                # Shell: > /dev/null || : (ignore errors, suppress output)
                # rm_run returns exit code, we ignore it to match shell behavior
                rm_run([*root_args, "-f", name])

            if delete:
                continue

        # Create
        print_msg(f" - Creating {name}...")

        # Check if exists (unless dry-run)
        if not parsed.dry_run:
            manager = detect_container_manager(
                preferred=config.container_manager,
                verbose=config.verbose,
                rootful=spec.root,
                sudo_program=config.sudo_program,
            )
            if manager.exists(name):
                print_error(f"{name} already exists")
                continue

        # Build create args
        create_args = _build_create_args(spec, config.verbose)

        if parsed.dry_run:
            # Print command matching shell format: sanitize each arg
            sanitized_args = [_sanitize_variable(arg) for arg in create_args]
            print(f"distrobox-create {' '.join(sanitized_args)}")
            continue

        result = create_run(create_args)
        if result != 0:
            continue

        # Start if needed
        if spec.start_now:
            enter_run([*root_args, "-n", name, "--", "touch", "/dev/null"])

        # Export apps/bins
        if spec.exported_apps or spec.exported_bins:
            # First ensure container is started
            enter_run([*root_args, "-n", name, "--", "touch", "/dev/null"])
            _run_exports(name, spec.root, spec, config.verbose)

    return 0


if __name__ == "__main__":
    sys.exit(run())
