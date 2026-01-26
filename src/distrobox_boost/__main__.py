"""CLI entry point for distrobox-boost."""

import argparse
import sys

from distrobox_boost.command import image


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="distrobox-boost",
        description="Tools for enhancing distrobox workflow",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # image subcommand
    image_parser = subparsers.add_parser(
        "image",
        help="Build a distrobox-ready container image",
    )
    image_parser.add_argument(
        "name",
        help="Name/tag for the resulting image",
    )
    image_parser.add_argument(
        "--base",
        required=True,
        help="Base image to build from (e.g., docker.io/library/fedora:latest)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "image":
        return image.run(args.name, args.base)

    return 0


if __name__ == "__main__":
    sys.exit(main())
