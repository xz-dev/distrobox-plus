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
With boost:   rebuild (once) → create → ready (fast)
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

### 2. Import and build optimized image

```bash
# Import your config
distrobox-boost assemble import --file mybox.ini --name mybox

# Build optimized image (run once, or when config changes)
distrobox-boost assemble rebuild mybox
```

### 3. Create container (fast!)

```bash
# Using assemble
distrobox-boost assemble mybox create

# Or using create directly (auto-detects boost image)
distrobox-boost create --name mybox --image archlinux:latest
```

## Commands

| Command | Description |
|---------|-------------|
| `assemble import --file <f> --name <n>` | Import original distrobox.ini config |
| `assemble rebuild <name>` | Build optimized image with baked packages/hooks |
| `assemble <name> create` | Create container using optimized config |
| `assemble <name> rm` | Remove container |
| `create [args...]` | Create container (uses boost image if available) |
| `enter`, `rm`, `list`, `stop`, ... | Passed through to distrobox |

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

**Impact:** This is your master config. Edit this file and run `rebuild` to apply changes.

### Cache Directory
`~/.cache/distrobox-boost/<container-name>/`

| File | Purpose |
|------|---------|
| `distrobox.ini` | Optimized config (auto-generated, uses local image) |
| `Containerfile` | Generated Containerfile (for debugging) |

**Impact:** These are auto-generated. Safe to delete - will be recreated on next `rebuild`.

### Container Images

Optimized images are stored in your container runtime (podman/docker) as `<name>:latest`.

```bash
# List boost images
podman images | grep -E '^[a-z]+\s+latest'

# Remove a boost image
podman rmi mybox:latest
```

## What Gets Baked?

When you run `rebuild`, these fields are baked into the image:

| Field | Baked? | Notes |
|-------|--------|-------|
| `image` | Yes | Base image, upgraded |
| `additional_packages` | Yes | Pre-installed |
| `init_hooks` | Yes | Pre-executed |
| `pre_init_hooks` | Yes | Pre-executed |
| `volume`, `nvidia`, etc. | No | Kept in optimized config |

The optimized config only contains non-baked fields plus a reference to your local image.

---

## Technical Details

### Architecture

```
src/distrobox_boost/
├── __main__.py              # CLI entry point and command routing
├── command/
│   ├── assemble.py          # import, rebuild, assemble commands
│   ├── create.py            # Intercepts create, substitutes boost image
│   └── passthrough.py       # Forwards commands to distrobox
└── utils/
    ├── config.py            # XDG directory management (platformdirs)
    ├── hijack.py            # PATH hijacking for distrobox-assemble
    ├── templates.py         # Cross-distro shell command generation
    └── utils.py             # Image builder detection
```

### How Hijacking Works

When `distrobox-assemble` runs, it internally calls `distrobox-create`. To intercept these calls, distrobox-boost uses PATH hijacking:

1. Creates a temporary directory with interceptor scripts
2. Symlinks `distrobox-assemble` to the real binary
3. Creates wrapper scripts that route `distrobox-create` → `distrobox-boost create`
4. Runs `distrobox-assemble` from this directory (uses `dirname $0` to find siblings)

```
/tmp/distrobox-boost-xxx/
├── distrobox-assemble  → /usr/bin/distrobox-assemble (symlink)
├── distrobox-create    → exec distrobox-boost create "$@"
└── distrobox           → routes 'create' to boost, others to real distrobox
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

`rebuild` generates a Containerfile with these steps:

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
| command/assemble.py | 46 | Full |
| command/create.py | 26 | Full |
| utils/hijack.py | 21 | Full |
| utils/templates.py | 15 | Full |
| utils/config.py | 20 | Full |
| utils/utils.py | 6 | Full |
| CLI (__main__.py) | 2 | Basic |
| Integration | 15 | 5 distros |

## License

BSD-3-Clause
