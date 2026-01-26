"""CLI entry point for distrobox-boost."""

import argparse
import sys

from distrobox_boost.command import assemble, image


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

    # assemble subcommand with sub-subcommands
    assemble_parser = subparsers.add_parser(
        "assemble",
        help="Run distrobox assemble with optimized config",
    )
    assemble_subparsers = assemble_parser.add_subparsers(dest="assemble_command")

    # assemble import
    import_parser = assemble_subparsers.add_parser(
        "import",
        help="Import original assemble file",
    )
    import_parser.add_argument(
        "--file",
        required=True,
        help="Path to original assemble file",
    )
    import_parser.add_argument(
        "--name",
        required=True,
        help="Container name (section name in the INI file)",
    )

    # assemble rebuild
    rebuild_parser = assemble_subparsers.add_parser(
        "rebuild",
        help="Build optimized image and generate assemble config",
    )
    rebuild_parser.add_argument(
        "name",
        help="Container name to rebuild",
    )

    # assemble <name> <args...> - passthrough to distrobox assemble
    assemble_parser.add_argument(
        "name",
        nargs="?",
        help="Container name",
    )
    assemble_parser.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
        help="Arguments to pass through to distrobox assemble (e.g., create, rm, create --dry-run)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "image":
        return image.run(args.name, args.base)

    if args.command == "assemble":
        if args.assemble_command == "import":
            return assemble.run_import(args.file, args.name)
        elif args.assemble_command == "rebuild":
            return assemble.run_rebuild(args.name)
        elif args.name:
            passthrough = args.passthrough if args.passthrough else []
            return assemble.run_assemble(args.name, passthrough)
        else:
            assemble_parser.print_help()
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
