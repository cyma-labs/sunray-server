# Muppy Development Layer Scripts

## Overview

This directory contains modular installation scripts for setting up development environments in both Docker containers and LXC/bare metal systems. Each script is idempotent (safe to re-run) and context-aware (adapts behavior based on execution environment).

## Location

All install scripts are located in `.muppy/scripts/` directory within the project.

## Numbering Scheme

Scripts use a numbered naming convention to enforce installation order and allow overriding:

**Format:** `mpy_install_XXX_name.sh`

**Layer Ranges:**
- **000-099**: Layer 0 - Base System (reserved for OS configuration)
- **100-199**: Layer 1 - System Minimum (remote admin tools, locale)
- **200-299**: Layer 2 - Development Minimum (build tools, compilers)
- **300-399**: Layer 3 - Platform-Specific Dev Tools (Node.js, Golang, Rust)
- **400-499**: Layer 4 - Database Clients (PostgreSQL, MySQL)
- **500-599**: Layer 5 - Application-Specific (Odoo dependencies)

**Purpose:**
- Numbers enforce execution order (100 runs before 300)
- Developers can override/extend by using sequential numbers within the same layer
- Example: `mpy_install_150_sys_extended.sh` would run after `100` but remain in Layer 1

**Current Scripts:**
- `mpy_install_100_sys_minimum.sh` - Layer 1: System utilities
- `mpy_install_300_nodejs_dev.sh` - Layer 3: Node.js development
- `mpy_install_350_docker.sh` - Layer 3: Docker CE and Docker Compose
- `mpy_install_400_pg_client.sh` - Layer 4: PostgreSQL client
- `mpy_install_450_dragonflydb.sh` - Layer 4: DragonflyDB (Redis-compatible cache)
- `mpy_install_500_odoo18_deps.sh` - Layer 5: Odoo 18 system dependencies
- `mpy_install_510_ikb.sh` - Layer 5: ikb (inouk buildit) installation

## Available Scripts

### mpy_install_100_sys_minimum.sh

**Layer 1 - System Minimum**

Installs system utilities for remote development and administration.

**Packages installed:**
- curl, wget - Download utilities
- iputils-ping - Network diagnostics
- htop - Process viewer
- tmux - Terminal multiplexer
- vim - Text editor
- software-properties-common - Package repository management
- ca-certificates - SSL certificates
- locales - Locale support (configured for en_US.UTF-8)
- less, unzip, tar, sudo - Essential utilities
- lsb-release - Distribution information

**Usage:**
```bash
sudo ./.muppy/scripts/mpy_install_100_sys_minimum.sh
```

**Environment variables:** None

### mpy_install_400_pg_client.sh

**Layer 4 - PostgreSQL Client**

Installs PostgreSQL client from the official PostgreSQL APT repository.

**Packages installed:**
- postgresql-client-{VERSION} - PostgreSQL command-line client
- libpq-dev - PostgreSQL development headers
- libjson-perl - JSON support for PostgreSQL

**Usage:**
```bash
# Install default version (16)
sudo ./.muppy/scripts/mpy_install_400_pg_client.sh

# Install specific version
sudo PG_VERSION=15 ./.muppy/scripts/mpy_install_400_pg_client.sh
```

**Environment variables:**
- `PG_VERSION` - PostgreSQL major version (default: 16)

### mpy_install_450_dragonflydb.sh

**Layer 4 - Database Services**

Installs redis-tools (redis-cli) and runs DragonflyDB as a Docker daemon for use as a Redis-compatible cache.

**Components installed:**
- redis-tools (redis-cli) - Always installed in all contexts
- DragonflyDB container - Only on VMs with Docker available

**Behavior:**
- **redis-tools**: Always installed (works in Docker, LXC, bare metal)
- **DragonflyDB**: Only runs on VMs (bare metal or LXC VM) where Docker is available
- **Graceful skip**: If Docker is not available, redis-tools is still installed and script exits successfully

**Usage:**
```bash
# Install with defaults (port 6379) - uses sudo internally
./.muppy/scripts/mpy_install_450_dragonflydb.sh

# Install with custom port
DRAGONFLY_PORT=6380 ./.muppy/scripts/mpy_install_450_dragonflydb.sh
```

**Post-installation:**
- Connect with: `redis-cli -h 127.0.0.1 -p 6379`
- Test connection: `redis-cli ping` (returns PONG)
- Check status: `docker ps --filter name=dragonflydb`
- View logs: `docker logs dragonflydb`
- Stop: `docker stop dragonflydb`
- Remove: `docker rm dragonflydb`

**Environment variables:**
- `DRAGONFLY_PORT` - Port to expose (default: 6379)

### mpy_install_300_nodejs_dev.sh

**Layer 3 - Node.js Development**

Installs Node.js LTS and npm from NodeSource official repository.

**Packages installed:**
- nodejs - Node.js runtime
- npm - Node package manager (included with nodejs)

**Usage:**
```bash
# Install default version (20.x LTS)
sudo ./.muppy/scripts/mpy_install_300_nodejs_dev.sh

# Install specific version
sudo NODE_VERSION=18 ./.muppy/scripts/mpy_install_300_nodejs_dev.sh
```

**Environment variables:**
- `NODE_VERSION` - Node.js major version (default: 20)

### mpy_install_350_docker.sh

**Layer 3 - Docker Development Environment**

Installs Docker CE and Docker Compose from official Docker repository. Only installs on bare metal VMs (skips in Docker/LXC contexts).

**Components installed:**
- Docker CE (Docker Engine)
- Docker CE CLI
- containerd.io
- Docker Buildx plugin
- Docker Compose plugin (v2)

**Important:** This script detects the execution context and only installs Docker on bare metal systems. In Docker or LXC containers, the script will log a message and exit gracefully without installing.

**Usage:**
```bash
# Install with defaults (uses sudo internally - DO NOT run with sudo)
./.muppy/scripts/mpy_install_350_docker.sh

# Specify user to add to docker group
MPY_USERNAME=myuser ./.muppy/scripts/mpy_install_350_docker.sh
```

**Important:** This script uses `sudo` internally and requires passwordless sudo. DO NOT run the script with `sudo` - run it as a regular user.

**Post-installation:**
- User must log out and back in for group changes to take effect
- Or run `newgrp docker` in current session
- Verify with: `docker run hello-world`

**Environment variables:**
- `MPY_USERNAME` - System username to add to docker group (default: $USER)

### mpy_install_500_odoo18_deps.sh

**Layer 5 - Odoo 18 System Dependencies**

Installs all Odoo 18-specific system dependencies including Python libraries, wkhtmltopdf, uv, and Python. This script requires sudo privileges and handles system-level installation.

**Components installed:**
- Python development libraries (Pillow, LDAP, compression)
- Font packages (for PDF rendering)
- wkhtmltopdf 0.12.6.1-3 (Odoo PDF tool)
- uv (Python package installer) - installed in `/opt/muppy/tools` with symlink to `/usr/local/bin/uv`
- Python 3.12.8 via uv
- /opt/muppy directory structure

**System-wide accessibility:**
- uv is installed in `/opt/muppy/tools` and symlinked to `/usr/local/bin/uv` for system-wide access
- All users can access `uv` without PATH modifications

**Usage:**
```bash
# Install with defaults (requires sudo)
sudo ./.muppy/scripts/mpy_install_500_odoo18_deps.sh

# Install with custom Python version
sudo IKB_PYTHON_VERSION=cpython@3.12.7 ./.muppy/scripts/mpy_install_500_odoo18_deps.sh
```

**Next step:**
After running this script, install ikb using [mpy_install_510_ikb.sh](#mpy_install_510_ikbsh) (run WITHOUT sudo).

**Environment variables:**
- `MPY_USERNAME` - System username (default: $USER)
- `MPY_APP_BASE_DIR` - Base directory (default: /opt/muppy)
- `IKB_PYTHON_VERSION` - Python version (default: cpython@3.12.8)
- `IKB_ODOO_VERSION` - Odoo major version (default: 18)

### mpy_install_510_ikb.sh

**Layer 5 - ikb (inouk buildit) Installation**

Installs ikb (inouk buildit) as a regular user WITHOUT sudo privileges. This script must be run AFTER [mpy_install_500_odoo18_deps.sh](#mpy_install_500_odoo18_depssh) to ensure uv is available.

**Important:** This script should NOT be run with sudo - it will exit with an error if run as root.

**Components installed:**
- ikb (inouk buildit - Odoo build tool) via `uv tool install`
- Symlink in `/opt/muppy/tools/ikb`
- System-wide symlink `/usr/local/bin/ikb` (uses sudo for this step only)

**Installation location:**
- ikb installs to user's `~/.local/share/uv/tools/inouk-buildit/`
- Symlink created in `/opt/muppy/tools/ikb` → `~/.local/share/uv/tools/inouk-buildit/bin/ikb`
- System-wide symlink `/usr/local/bin/ikb` → `/opt/muppy/tools/ikb`

**Usage:**
```bash
# Install ikb (run WITHOUT sudo, as regular user)
./.muppy/scripts/mpy_install_510_ikb.sh

# Install ikb in development mode
IKB_DEV_MODE=True ./.muppy/scripts/mpy_install_510_ikb.sh

# Install with custom Python version
IKB_PYTHON_VERSION=cpython@3.12.7 ./.muppy/scripts/mpy_install_510_ikb.sh
```

**Error handling:**
- Script exits with error if run with sudo
- Script exits with error if uv is not available
- Script uninstalls previous ikb installation before fresh install

**Environment variables:**
- `MPY_APP_BASE_DIR` - Base directory (default: /opt/muppy)
- `IKB_PYTHON_VERSION` - Python version (default: cpython@3.12.8)
- `IKB_DEV_MODE` - Install ikb in dev mode (default: False)

## Script Features

### Idempotency

All scripts check if software is already installed before proceeding:
- If the correct version is already installed, the script exits immediately
- Safe to run multiple times without side effects
- Helpful for CI/CD pipelines and automated provisioning

### Context Detection

Scripts automatically detect the execution environment:
- **Docker**: Cleans up apt cache to reduce image size
- **LXC**: Preserves apt cache for faster re-runs
- **Bare metal**: Preserves apt cache for faster re-runs

### Error Handling

- Exit code 0: Success (installed or already present)
- Exit code 1: Installation failed or missing dependencies
- All scripts require sudo/root privileges
- Clear error messages for troubleshooting

### Logging

Scripts provide informative output:
- `[INFO]` - Informational messages
- `[SUCCESS]` - Successful operations
- `[ERROR]` - Error conditions
- Version verification after installation

## Testing

All scripts have been tested in:
- ✓ Docker build context
- ✓ LXC containers
- ✓ Ubuntu 24.04 LTS bare metal
- ✓ Idempotency (multiple runs)
- ✓ Different versions via environment variables

## Usage Examples

### Docker Integration

```dockerfile
# System minimum layer
COPY .muppy/scripts/mpy_install_100_sys_minimum.sh /tmp/
RUN /tmp/mpy_install_100_sys_minimum.sh && rm /tmp/mpy_install_100_sys_minimum.sh

# PostgreSQL client layer
COPY .muppy/scripts/mpy_install_400_pg_client.sh /tmp/
RUN PG_VERSION=16 /tmp/mpy_install_400_pg_client.sh && rm /tmp/mpy_install_400_pg_client.sh

# Node.js development layer
COPY .muppy/scripts/mpy_install_300_nodejs_dev.sh /tmp/
RUN /tmp/mpy_install_300_nodejs_dev.sh && rm /tmp/mpy_install_300_nodejs_dev.sh
```

### LXC/Bare Metal Setup

```bash
# Navigate to project directory
cd /opt/muppy/workspace-sunray/appserver-sunray18

# Run scripts in order (with sudo)
sudo ./.muppy/scripts/mpy_install_100_sys_minimum.sh
sudo ./.muppy/scripts/mpy_install_300_nodejs_dev.sh
./.muppy/scripts/mpy_install_350_docker.sh  # Uses sudo internally
sudo ./.muppy/scripts/mpy_install_400_pg_client.sh
sudo ./.muppy/scripts/mpy_install_500_odoo18_deps.sh

# Install ikb (WITHOUT sudo, as regular user)
./.muppy/scripts/mpy_install_510_ikb.sh

# Verify installations
psql --version
node --version
npm --version
docker --version
docker compose version
uv --version
ikb 2>&1 | head -3
which curl vim tmux docker uv ikb
locale
```

### CI/CD Integration

```yaml
# Example GitHub Actions workflow
steps:
  - name: Setup system
    run: sudo ./.muppy/scripts/mpy_install_100_sys_minimum.sh

  - name: Install PostgreSQL client
    run: sudo PG_VERSION=16 ./.muppy/scripts/mpy_install_400_pg_client.sh

  - name: Install Node.js
    run: sudo NODE_VERSION=20 ./.muppy/scripts/mpy_install_300_nodejs_dev.sh
```

## Troubleshooting

### Permission Denied

```bash
# Error: Permission denied
# Solution: Run with sudo
sudo ./.muppy/scripts/mpy_install_400_pg_client.sh
```

### Already Installed Message

```bash
# Message: "PostgreSQL client 16 already installed, skipping..."
# This is normal - the script detected existing installation
# To force reinstall, uninstall first:
sudo apt-get remove postgresql-client-16
```

### Version Mismatch

```bash
# If different version is installed, script will proceed with upgrade
# Example: v18.x installed, script installs v20.x (NODE_VERSION=20)
```

## Architecture Notes

These scripts follow the **Manganese Development Layer Architecture**:
- **Layer 0** (000-099): Base System / Ubuntu LTS (reserved for OS configuration)
- **Layer 1** (100-199): System Minimum (this directory: [mpy_install_100_sys_minimum.sh](mpy_install_100_sys_minimum.sh))
- **Layer 2** (200-299): Development Minimum (future: build tools, Python, compilers)
- **Layer 3** (300-399): Platform-Specific Dev Tools
  - [mpy_install_300_nodejs_dev.sh](mpy_install_300_nodejs_dev.sh) - Node.js development
  - [mpy_install_350_docker.sh](mpy_install_350_docker.sh) - Docker CE and Docker Compose
- **Layer 4** (400-499): Database Clients & Services
  - [mpy_install_400_pg_client.sh](mpy_install_400_pg_client.sh) - PostgreSQL client
  - [mpy_install_450_dragonflydb.sh](mpy_install_450_dragonflydb.sh) - DragonflyDB (Docker daemon)
- **Layer 5** (500-599): Application-Specific
  - [mpy_install_500_odoo18_deps.sh](mpy_install_500_odoo18_deps.sh) - System dependencies (requires sudo)
  - [mpy_install_510_ikb.sh](mpy_install_510_ikb.sh) - User tools (run WITHOUT sudo)

## Numbering Rationale

The numbering scheme follows the **Manganese Development Layer Architecture**:
- **Enforces dependency order**: System tools (100) install before development tools (300)
- **Enables overriding**: A script numbered `305` would run after `300` in the same layer
- **Clear layer boundaries**: Each 100-number range represents a distinct architectural layer
- **Future extensibility**: Reserved ranges allow adding new layers without renaming existing scripts

## Version History

- **v1.5** - DragonflyDB cache service (2025-12)
  - Added mpy_install_450_dragonflydb.sh (Layer 4)
  - DragonflyDB as Docker daemon for Redis-compatible caching
  - Cache-only mode (no persistence)
  - Requires Docker (mpy_install_350_docker.sh)
- **v1.4** - Docker development environment (2025-11)
  - Added mpy_install_350_docker.sh (Layer 3)
  - Docker CE and Docker Compose from official repos
  - Context-aware: only installs on bare metal VMs
  - User added to docker group for non-root access
- **v1.3** - Separated ikb installation (2025-11)
  - Split ikb installation into separate script (mpy_install_510_ikb.sh)
  - Two-script approach: system deps (sudo) vs user tools (no sudo)
  - System-wide accessibility via symlinks to /usr/local/bin
  - mpy_install_500_odoo18_deps.sh: installs uv, wkhtmltopdf, Python (requires sudo)
  - mpy_install_510_ikb.sh: installs ikb (run WITHOUT sudo)
  - Improved permissions handling and security separation
- **v1.2** - Odoo 18 dependencies layer (2025-11)
  - Added mpy_install_500_odoo18_deps.sh (Layer 5)
  - Comprehensive Odoo 18 development environment setup
  - Python libraries, wkhtmltopdf, uv, ikb installation
- **v1.1** - Numbering scheme (2025-11)
  - Renamed scripts with numbered prefixes (100, 300, 400)
  - Added numbering scheme documentation
  - Updated layer architecture alignment
- **v1.0** - Initial release (2025-01)
  - mpy_install_100_sys_minimum.sh (formerly mpy_install_sys_minimum.sh)
  - mpy_install_400_pg_client.sh (formerly mpy_install_pg_client.sh)
  - mpy_install_300_nodejs_dev.sh (formerly mpy_install_nodejs_dev.sh)

## Contributing

When adding new scripts:
1. Follow the existing header format (SCRIPT, LAYER, PURPOSE, USAGE, ENV VARS, etc.)
2. Implement idempotency checks
3. Add context detection for Docker/LXC
4. Include error handling and verification
5. Update this README.md
6. Test in Docker and LXC environments

## Related Documentation

- Main project: [../../README.md](../../README.md)
- Development guide: [../../CLAUDE.md](../../CLAUDE.md)
- Architecture specification: [../../specs_server/manganese-dev-draft.md](../../specs_server/manganese-dev-draft.md)
