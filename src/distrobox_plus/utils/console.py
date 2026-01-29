"""Rich console utilities for distrobox-plus."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.table import Table
from rich.theme import Theme

# Custom theme matching distrobox colors
DISTROBOX_THEME = Theme({
    "ok": "green",
    "error": "bold red",
    "warning": "yellow",
    "container.running": "green",
    "container.stopped": "yellow",
})

# stdout console
console = Console(theme=DISTROBOX_THEME)

# stderr console
err_console = Console(stderr=True, theme=DISTROBOX_THEME)


def print_msg(message: str) -> None:
    """Print message to stdout."""
    console.print(message)


def print_error(message: str, end: str = "\n") -> None:
    """Print message to stderr."""
    err_console.print(message, end=end)


def print_status(message: str, end: str = "") -> None:
    """Print status message to stderr (padded, no newline by default)."""
    err_console.print(f"{message:<40}", end=end)


def yellow(text: str) -> str:
    """Return text wrapped in yellow markup."""
    return f"[warning]{text}[/warning]"


def red(text: str) -> str:
    """Return text wrapped in red/error markup."""
    return f"[error]{text}[/error]"


def green(text: str) -> str:
    """Return text wrapped in green/ok markup."""
    return f"[ok]{text}[/ok]"


def create_container_table() -> Table:
    """Create a table for container listing.

    Note: no_wrap=True ensures each row stays on one line for script parsing.
    No fixed width is set so columns auto-expand to fit content.
    """
    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("ID", no_wrap=True)
    table.add_column("NAME", no_wrap=True)
    table.add_column("STATUS", no_wrap=True)
    table.add_column("IMAGE", no_wrap=True)
    return table


def is_tty() -> bool:
    """Check if stdin and stdout are connected to a TTY."""
    return sys.stdin.isatty() and sys.stdout.isatty()
