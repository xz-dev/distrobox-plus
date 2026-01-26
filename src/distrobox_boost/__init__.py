def main() -> int:
    """Entry point wrapper to avoid import warnings."""
    from distrobox_boost.__main__ import main as _main
    return _main()

__all__ = ["main"]
