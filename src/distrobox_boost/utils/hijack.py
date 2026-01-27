"""Hijack directory manager for intercepting distrobox internal calls.

distrobox-boost acts as a shim for distrobox. When ephemeral/assemble call
internal commands like distrobox-create, we intercept them to apply boost
optimizations (auto-build images, replace parameters, etc.).

Hijack directory structure:
    /tmp/distrobox-boost-xxx/
    ├── distrobox           → routes all subcommands to distrobox-boost
    ├── distrobox-create    → exec distrobox-boost create "$@"
    ├── distrobox-assemble  → exec distrobox-boost assemble "$@"
    ├── distrobox-ephemeral → exec distrobox-boost ephemeral "$@"
    ├── distrobox-enter     → exec distrobox-boost enter "$@"
    ├── distrobox-rm        → exec distrobox-boost rm "$@"
    ├── distrobox-stop      → exec distrobox-boost stop "$@"
    ├── distrobox-list      → exec distrobox-boost list "$@"
    ├── distrobox-upgrade   → exec distrobox-boost upgrade "$@"
    └── distrobox-generate-entry → exec distrobox-boost generate-entry "$@"
"""

import os
import stat
import tempfile
from pathlib import Path
from types import TracebackType

# All distrobox commands that need to be hijacked
DISTROBOX_COMMANDS = [
    "create",
    "assemble",
    "ephemeral",
    "enter",
    "rm",
    "stop",
    "list",
    "upgrade",
    "generate-entry",
]


class HijackManager:
    """Context manager that creates a hijack directory for command interception.

    All distrobox commands are routed through distrobox-boost, allowing us to
    intercept and modify command behavior (especially create commands).

    Usage:
        with HijackManager() as hijack:
            subprocess.run([str(hijack.distrobox_path), "ephemeral", "--image", "alpine"])
    """

    def __init__(self) -> None:
        """Initialize the hijack manager."""
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._hijack_dir: Path | None = None

    @property
    def hijack_dir(self) -> Path:
        """Get the hijack directory path."""
        if self._hijack_dir is None:
            raise RuntimeError("HijackManager not entered as context manager")
        return self._hijack_dir

    @property
    def distrobox_path(self) -> Path:
        """Get the path to the hijacked distrobox command."""
        return self.hijack_dir / "distrobox"

    @property
    def env(self) -> dict[str, str]:
        """Get environment with hijack directory prepended to PATH."""
        env = os.environ.copy()
        env["PATH"] = f"{self.hijack_dir}:{env.get('PATH', '')}"
        return env

    def __enter__(self) -> "HijackManager":
        """Create the hijack directory with interceptor scripts."""
        self._tmpdir = tempfile.TemporaryDirectory(prefix="distrobox-boost-")
        self._hijack_dir = Path(self._tmpdir.name)

        # Create interceptor scripts for all commands
        for cmd in DISTROBOX_COMMANDS:
            self._create_command_interceptor(cmd)

        # Create the main distrobox router
        self._create_distrobox_router()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Clean up the hijack directory."""
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None
            self._hijack_dir = None

    def _create_command_interceptor(self, command: str) -> None:
        """Create an interceptor script for a distrobox command.

        All commands are routed to distrobox-boost <command>.

        Args:
            command: Command name (e.g., "create", "ephemeral").
        """
        script_path = self._hijack_dir / f"distrobox-{command}"

        # Route to distrobox-boost
        script_content = f'#!/bin/sh\nexec distrobox-boost {command} "$@"\n'

        script_path.write_text(script_content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _create_distrobox_router(self) -> None:
        """Create a router script for the main distrobox command.

        Routes all subcommands to distrobox-boost.
        """
        script_path = self._hijack_dir / "distrobox"

        # Build case statement for all commands
        case_branches = []
        for cmd in DISTROBOX_COMMANDS:
            case_branches.append(f'    {cmd})\n        shift\n        exec distrobox-boost {cmd} "$@"\n        ;;')

        case_statement = "\n".join(case_branches)

        # Script that routes known subcommands to distrobox-boost
        # Unknown commands (like --help, --version) pass through to real distrobox
        script_content = f'''#!/bin/sh
# Router script: intercept known subcommands, pass others through
case "$1" in
{case_statement}
    *)
        # Find real distrobox by searching PATH (excluding this directory)
        REAL_DISTROBOX=""
        OLD_IFS="$IFS"
        IFS=":"
        for dir in $PATH; do
            if [ "$dir" != "{self._hijack_dir}" ] && [ -x "$dir/distrobox" ]; then
                REAL_DISTROBOX="$dir/distrobox"
                break
            fi
        done
        IFS="$OLD_IFS"
        if [ -n "$REAL_DISTROBOX" ]; then
            exec "$REAL_DISTROBOX" "$@"
        else
            echo "Error: distrobox not found in PATH" >&2
            exit 1
        fi
        ;;
esac
'''
        script_path.write_text(script_content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
