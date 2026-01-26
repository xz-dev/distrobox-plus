"""Create command: intercept distrobox create and apply boost optimizations."""

import subprocess

from distrobox_boost.utils.config import get_container_cache_dir


def extract_arg_value(args: list[str], flags: list[str]) -> str | None:
    """Extract the value of a flag from an argument list.

    Supports both '--flag value' and '--flag=value' formats.

    Args:
        args: List of command-line arguments.
        flags: List of flag names to look for (e.g., ["--name", "-n"]).

    Returns:
        The flag's value if found, None otherwise.
    """
    for i, arg in enumerate(args):
        # Check --flag value format
        if arg in flags and i + 1 < len(args):
            return args[i + 1]
        # Check --flag=value format
        for flag in flags:
            if arg.startswith(f"{flag}="):
                return arg.split("=", 1)[1]
    return None


def replace_arg_value(args: list[str], flags: list[str], new_value: str) -> list[str]:
    """Replace the value of a flag in an argument list.

    Supports both '--flag value' and '--flag=value' formats.

    Args:
        args: List of command-line arguments.
        flags: List of flag names to look for (e.g., ["--image", "-i"]).
        new_value: New value to set for the flag.

    Returns:
        New argument list with the replaced value.
    """
    result: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]

        # Check --flag value format
        if arg in flags:
            result.append(arg)
            result.append(new_value)
            i += 2  # Skip the original value
            continue

        # Check --flag=value format
        replaced = False
        for flag in flags:
            if arg.startswith(f"{flag}="):
                result.append(f"{flag}={new_value}")
                replaced = True
                break

        if not replaced:
            result.append(arg)
        i += 1

    return result


def remove_args(args: list[str], flags: list[str]) -> list[str]:
    """Remove specified flags and their values from an argument list.

    Supports both '--flag value' and '--flag=value' formats.

    Args:
        args: List of command-line arguments.
        flags: List of flag names to remove (e.g., ["--additional-packages", "-ap"]).

    Returns:
        New argument list with the flags and their values removed.
    """
    result: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]

        # Check --flag value format
        if arg in flags:
            i += 2  # Skip both flag and value
            continue

        # Check --flag=value format
        skip = False
        for flag in flags:
            if arg.startswith(f"{flag}="):
                skip = True
                break

        if not skip:
            result.append(arg)
        i += 1

    return result


def has_boost_image(name: str) -> bool:
    """Check if a boost-optimized config exists for the given container.

    Args:
        name: Container name.

    Returns:
        True if an optimized distrobox.ini exists.
    """
    cache_dir = get_container_cache_dir(name)
    config_path = cache_dir / "distrobox.ini"
    return config_path.exists()


def get_boost_image(name: str) -> str:
    """Get the boost image name for a container.

    The image name follows the convention: {name}:latest

    Args:
        name: Container name.

    Returns:
        Image tag for the boost-optimized image.
    """
    return f"{name}:latest"


# Flags that are baked into the optimized image and should be removed
BAKED_FLAGS = [
    "--additional-packages",
    "-ap",
    "--init-hooks",
    "--pre-init-hooks",
]


def run_create(args: list[str]) -> int:
    """Run distrobox create with boost optimizations applied.

    If a boost-optimized image exists for the container, this function:
    - Replaces --image with the optimized image
    - Removes flags that were baked into the image

    Args:
        args: Command-line arguments (excluding 'create' itself).

    Returns:
        Exit code from distrobox create.
    """
    # Extract container name
    name = extract_arg_value(args, ["--name", "-n"])

    if name and has_boost_image(name):
        print(f"[distrobox-boost] Using optimized image for '{name}'")
        new_image = get_boost_image(name)

        # Replace image and remove baked-in flags
        args = replace_arg_value(args, ["--image", "-i"], new_image)
        args = remove_args(args, BAKED_FLAGS)

    # Pass through to real distrobox create
    cmd = ["distrobox", "create", *args]
    result = subprocess.run(cmd)
    return result.returncode
