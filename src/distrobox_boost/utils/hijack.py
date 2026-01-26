"""Hijack directory manager for intercepting distrobox-assemble's internal calls."""

import os
import shutil
import stat
import tempfile
from pathlib import Path
from types import TracebackType


class HijackManager:
    """Context manager that creates a hijack directory for PATH interception.

    distrobox-assemble uses `dirname "$0"` to find related commands like
    distrobox-create. By creating a temporary directory with:
    - A symlink to the real distrobox-assemble
    - Wrapper scripts for commands we want to intercept

    We can make distrobox-assemble call our code instead of the original.

    Usage:
        with HijackManager() as hijack:
            subprocess.run([str(hijack.assemble_path), "create", "--file", config])
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
    def assemble_path(self) -> Path:
        """Get the path to the hijacked distrobox-assemble."""
        return self.hijack_dir / "distrobox-assemble"

    def __enter__(self) -> "HijackManager":
        """Create the hijack directory with interceptor scripts."""
        self._tmpdir = tempfile.TemporaryDirectory(prefix="distrobox-boost-")
        self._hijack_dir = Path(self._tmpdir.name)

        # Find the real distrobox-assemble
        real_assemble = shutil.which("distrobox-assemble")
        if real_assemble is None:
            raise RuntimeError("distrobox-assemble not found in PATH")

        # Symlink distrobox-assemble so dirname works correctly
        os.symlink(real_assemble, self._hijack_dir / "distrobox-assemble")

        # Create interceptor for distrobox-create (routes to distrobox-boost create)
        self._create_interceptor("distrobox-create", intercept=True)

        # Create interceptor for distrobox command (routes create subcommand)
        self._create_distrobox_router()

        # Create passthroughs for other commands that assemble might call
        for cmd in ["distrobox-list", "distrobox-enter", "distrobox-rm", "distrobox-stop"]:
            self._create_interceptor(cmd, intercept=False)

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

    def _create_interceptor(self, name: str, *, intercept: bool) -> None:
        """Create an interceptor script for a distrobox command.

        Args:
            name: Command name (e.g., "distrobox-create").
            intercept: If True, route to distrobox-boost create.
                       If False, pass through to real command.
        """
        script_path = self._hijack_dir / name

        if intercept:
            # Route to distrobox-boost create
            script_content = '#!/bin/sh\nexec distrobox-boost create "$@"\n'
        else:
            # Find and exec the real command
            real_cmd = shutil.which(name)
            if real_cmd is None:
                # If command doesn't exist, create a script that errors gracefully
                script_content = f'#!/bin/sh\necho "Error: {name} not found" >&2\nexit 1\n'
            else:
                script_content = f'#!/bin/sh\nexec "{real_cmd}" "$@"\n'

        script_path.write_text(script_content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _create_distrobox_router(self) -> None:
        """Create a router script for the main distrobox command.

        Routes 'distrobox create' to distrobox-boost, other subcommands pass through.
        """
        script_path = self._hijack_dir / "distrobox"

        real_distrobox = shutil.which("distrobox")
        if real_distrobox is None:
            raise RuntimeError("distrobox not found in PATH")

        # Script that intercepts 'create' subcommand
        script_content = f'''#!/bin/sh
# Router script: intercept 'create' subcommand, pass others through
if [ "$1" = "create" ]; then
    shift
    exec distrobox-boost create "$@"
else
    exec "{real_distrobox}" "$@"
fi
'''
        script_path.write_text(script_content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
