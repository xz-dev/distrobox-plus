# distrobox-boost

Accelerate distrobox container creation by baking packages and hooks into optimized images.

## Why distrobox-boost?

Every time you create a distrobox container, it needs to:
1. Pull the base image
2. Install distrobox dependencies
3. Install your additional packages
4. Execute init hooks

This can take several minutes. **distrobox-boost** pre-bakes all of this into a local image, reducing container creation time to seconds.

```
Traditional:  create → pull → install deps → install packages → run hooks → ready (slow)
With boost:   create → ready (fast, image built automatically on first run)
```

## Installation

```bash
# Using pipx (recommended)
pipx install distrobox-boost

# Using pip
pip install --user distrobox-boost

# From source
git clone https://github.com/xz-dev/distrobox-boost
cd distrobox-boost
pip install .
```

**Requirements:**
- Python 3.13+
- distrobox
- Container runtime: buildah, podman, or docker

## Quick Start

### 1. Create a distrobox assemble config

```ini
# mybox.ini
[mybox]
image=archlinux:latest
additional_packages=git neovim nodejs npm
init_hooks="echo 'Container initialized'"
volume=/home/user:/home/user
```

### 2. Import config

```bash
# Import your config
distrobox-boost assemble import --file mybox.ini --name mybox
```

### 3. Create container (fast!)

```bash
# Using assemble (image is built automatically on first run)
distrobox-boost assemble create --file mybox.ini

# Or using create directly (auto-detects and builds boost image)
distrobox-boost create --name mybox --image archlinux:latest

# Or using ephemeral (internal create is automatically optimized)
distrobox-boost ephemeral --name mybox --image archlinux:latest
```

## Commands

| Command | Description |
|---------|-------------|
| `assemble import --file <f> --name <n>` | Import original distrobox.ini config |
| `assemble [args...]` | Run distrobox assemble (with auto-optimization) |
| `create [args...]` | Create container (auto-builds boost image if config exists) |
| `ephemeral [args...]` | Run ephemeral (internal create is auto-optimized) |
| `enter`, `rm`, `list`, `stop`, ... | Passed through to distrobox |

## How It Works (Shim Architecture)

distrobox-boost acts as a **shim** for distrobox. When you run any command:

```
User: distrobox-boost ephemeral --image alpine --name mybox
                  ↓
        [ephemeral runs with PATH hijacking]
                  ↓
        ephemeral internally calls distrobox-create
                  ↓
        [hijacked → distrobox-boost create]
                  ↓
        [create pre-hook: detect config → build image → replace args]
                  ↓
        [real distrobox-create runs with optimized image]
```

The magic happens in the `create` pre-hook:
1. Checks if a config exists for the container name
2. Builds the optimized image if needed (automatically, on first run)
3. Replaces `--image` with the boost image
4. Removes flags that were baked in (`--additional-packages`, `--init-hooks`, etc.)

## Data Storage

distrobox-boost stores data in two locations following XDG conventions:

### Config Directory
`~/.config/distrobox-boost/<container-name>/`

| File | Purpose |
|------|---------|
| `distrobox.ini` | Stored config without section header (your source of truth) |

The container name is determined by the directory name, not the file content:

```ini
# ~/.config/distrobox-boost/mybox/distrobox.ini
# Note: No [mybox] section header - the directory name IS the container name
image=archlinux:latest
additional_packages=git neovim nodejs npm
init_hooks="echo 'Container initialized'"
volume=/home/user:/home/user
```

**Impact:** This is your master config. Edit this file to change settings.

### Cache Directory
`~/.cache/distrobox-boost/<container-name>/`

| File | Purpose |
|------|---------|
| `Containerfile` | Generated Containerfile (for debugging) |

**Impact:** Auto-generated. Safe to delete - will be recreated on next build.

### Container Images

Optimized images are stored in your container runtime (podman/docker) as `<name>:latest`.

```bash
# List boost images
podman images | grep -E '^[a-z]+\s+latest'

# Remove a boost image (will be rebuilt on next create)
podman rmi mybox:latest
```

## What Gets Baked?

When the image is built (automatically on first create), these fields are baked into the image:

| Field | Baked? | Notes |
|-------|--------|-------|
| `image` | Yes | Base image, upgraded |
| `additional_packages` | Yes | Pre-installed |
| `init_hooks` | Yes | Pre-executed |
| `pre_init_hooks` | Yes | Pre-executed |
| `volume`, `nvidia`, etc. | No | Kept in config |

---

## Technical Details

### Architecture

```
src/distrobox_boost/
├── __main__.py              # CLI entry point and command routing
├── command/
│   ├── assemble.py          # import subcommand, assemble passthrough
│   ├── create.py            # create pre-hook (core magic: auto-build + arg substitution)
│   └── wrapper.py           # Generic pre/post hook framework
└── utils/
    ├── builder.py           # Image building logic
    ├── config.py            # XDG directory management (platformdirs)
    ├── hijack.py            # PATH hijacking for all distrobox commands
    ├── templates.py         # Cross-distro shell command generation
    └── utils.py             # Image builder detection
```

### How Hijacking Works

When commands like `distrobox-assemble` or `distrobox-ephemeral` run, they internally call `distrobox-create`. To intercept these calls, distrobox-boost uses PATH hijacking:

1. Creates a temporary directory with interceptor scripts for ALL distrobox commands
2. Each script routes to `distrobox-boost <command>`
3. Runs the original command with this directory prepended to PATH
4. The `create` command has a pre-hook that applies optimizations

```
/tmp/distrobox-boost-xxx/
├── distrobox           → routes subcommands to distrobox-boost
├── distrobox-create    → exec distrobox-boost create "$@"
├── distrobox-assemble  → exec distrobox-boost assemble "$@"
├── distrobox-ephemeral → exec distrobox-boost ephemeral "$@"
├── distrobox-enter     → exec distrobox-boost enter "$@"
├── distrobox-rm        → exec distrobox-boost rm "$@"
└── ...
```

### Cross-Distribution Support

distrobox-boost generates shell scripts that auto-detect the package manager:

| Distribution | Package Manager | Detection |
|--------------|-----------------|-----------|
| Alpine | apk | `command -v apk` |
| Debian/Ubuntu | apt-get | `command -v apt-get` |
| Fedora/RHEL | dnf/microdnf/yum | `command -v dnf` |
| Arch | pacman | `command -v pacman` |
| openSUSE | zypper | `command -v zypper` |

The generated Containerfile includes conditional logic to handle any supported distribution.

### Image Build Process

When the image is built, the Containerfile includes these steps:

1. **Upgrade** - Update all system packages
2. **Pre-init hooks** - Run user-defined pre-initialization commands
3. **Install dependencies** - Install distrobox required packages
4. **Additional packages** - Install user-specified packages
5. **Init hooks** - Run user-defined initialization commands

Each step uses distribution-aware commands generated at build time.

## Development

```bash
# Clone and install in development mode
git clone https://github.com/xz-dev/distrobox-boost
cd distrobox-boost
pip install -e ".[dev]"

# Run tests (default: unit tests + alpine integration)
uv run pytest -v

# Run all tests including slow distro builds (debian, fedora, arch, opensuse)
uv run pytest -v -m ""

# Run only unit tests (no integration)
uv run pytest -v --ignore=tests/test_integration.py
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| command/assemble.py | 35 | Full |
| command/create.py | 30 | Full |
| command/wrapper.py | - | Tested via other modules |
| utils/builder.py | - | Tested via assemble |
| utils/hijack.py | 18 | Full |
| utils/templates.py | 15 | Full |
| utils/config.py | 20 | Full |
| utils/utils.py | 6 | Full |
| Integration | 15 | 5 distros |

## License

BSD-3-Clause
