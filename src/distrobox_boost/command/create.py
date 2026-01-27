"""Create command: intercept distrobox create and apply boost optimizations.

This is where the core magic happens. When a create command is intercepted,
we check if there's a config file for the container and automatically:
1. Build the optimized image if needed
2. Replace the --image argument with our boost image
3. Remove flags that were baked into the image
"""

from distrobox_boost.command.wrapper import run_with_hooks
from distrobox_boost.utils.builder import (
    ensure_boost_image,
    get_boost_image_name,
    has_config,
    needs_rebuild,
)


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


# Flags that are baked into the optimized image and should be removed
BAKED_FLAGS = [
    "--additional-packages",
    "-ap",
    "--init-hooks",
    "--pre-init-hooks",
]


def create_pre_hook(args: list[str]) -> list[str] | None:
    """Pre-hook for create command - the core magic.

    This hook:
    1. Extracts the container name from args
    2. Checks if we have a config for this container
    3. Builds the optimized image if needed
    4. Replaces --image with our boost image
    5. Removes flags that were baked in

    Args:
        args: Original command arguments.

    Returns:
        Modified arguments, or None to use original args.
    """
    # Extract container name
    name = extract_arg_value(args, ["--name", "-n"])

    if not name:
        # Can't optimize without a name
        return None

    if not has_config(name):
        # No config for this container, pass through unchanged
        return None

    # Check if we need to build the image
    if needs_rebuild(name):
        print(f"[distrobox-boost] Building optimized image for '{name}'...")
        result = ensure_boost_image(name)
        if result != 0:
            print(f"[distrobox-boost] Build failed, falling back to original image")
            return None

    # Get the boost image name
    new_image = get_boost_image_name(name)

    print(f"[distrobox-boost] Using optimized image '{new_image}' for '{name}'")

    # Replace image and remove baked-in flags
    modified_args = replace_arg_value(args, ["--image", "-i"], new_image)
    modified_args = remove_args(modified_args, BAKED_FLAGS)

    return modified_args


def run_create(args: list[str]) -> int:
    """Run distrobox create with boost optimizations applied.

    This uses the wrapper framework with our create_pre_hook.
    The hook automatically builds images and substitutes parameters.

    Args:
        args: Command-line arguments (excluding 'create' itself).

    Returns:
        Exit code from distrobox create.
    """
    return run_with_hooks(
        "create",
        args,
        pre_hook=create_pre_hook,
        use_hijack=False,  # create doesn't call other distrobox commands internally
    )
