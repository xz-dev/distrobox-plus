# distrobox-plus

A Python implementation of [distrobox](https://github.com/89luca89/distrobox) for creating and managing containerized development environments.

## Features

- Full compatibility with original distrobox
- Supports podman, docker, and lilipod container managers
- All major commands implemented:
  - `create` - Create a new container
  - `enter` - Enter a container
  - `list` - List containers
  - `rm` - Remove containers
  - `stop` - Stop containers
  - `upgrade` - Upgrade containers
  - `assemble` - Create containers from manifest file
  - `ephemeral` - Create temporary containers
  - `export` - Export apps/services from container
  - `generate-entry` - Generate desktop entry

## Requirements

- Python 3.10+
- One of: podman, docker, or lilipod

## Installation

```bash
# Using uv (recommended)
uv tool install distrobox-plus

# Using pip
pip install distrobox-plus
```

## Usage

```bash
# Create a container
distrobox-plus create --image ubuntu:22.04 --name my-ubuntu

# Enter the container
distrobox-plus enter my-ubuntu

# List containers
distrobox-plus list

# Remove a container
distrobox-plus rm my-ubuntu
```

## Development

```bash
# Clone the repository
git clone https://github.com/xz-dev/distrobox-plus
cd distrobox-plus

# Install development dependencies
uv sync --group dev

# Run tests
uv run pytest

# Run fast tests only
uv run pytest -m fast
```

## License

BSD 3-Clause License. See [LICENSE](LICENSE) for details.

## Acknowledgments

This project is a Python reimplementation of [distrobox](https://github.com/89luca89/distrobox) by Luca Di Maio.
