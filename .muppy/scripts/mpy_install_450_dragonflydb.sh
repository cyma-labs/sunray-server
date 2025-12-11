#!/usr/bin/env bash
set -euo pipefail

# SCRIPT: mpy_install_450_dragonflydb.sh
# LAYER: 4 - Database Services
# PURPOSE: Install redis-tools and run DragonflyDB as Docker daemon (cache-only)
# USAGE: ./mpy_install_450_dragonflydb.sh (uses sudo internally)
# ENV VARS:
#   - DRAGONFLY_PORT: Port to expose (default: 6379)
# REQUIREMENTS: VM environment for DragonflyDB (redis-tools installs everywhere), passwordless sudo
# EXIT CODES:
#   0 - Success (redis-tools installed, DragonflyDB running or skipped)
#   1 - redis-tools installation failed

# Configuration
DRAGONFLY_PORT="${DRAGONFLY_PORT:-6379}"
CONTAINER_NAME="dragonflydb"
DRAGONFLY_IMAGE="docker.dragonflydb.io/dragonflydb/dragonfly"

# Detect execution context (Docker vs LXC container vs LXC VM vs bare metal)
detect_context() {
  # Docker detection
  if [ -f /.dockerenv ]; then
    echo "docker"
    return
  fi

  # LXC detection
  if [ -d /dev/lxd ]; then
    # Distinguish between LXC VM (--vm, has own kernel) and LXC container
    # LXC VMs have DMI tables like real VMs, containers don't
    if [ -d /sys/class/dmi/id ]; then
      echo "lxc_vm"
      return
    fi
    echo "lxc_container"
    return
  fi

  echo "bare_metal"
}

CONTEXT=$(detect_context)
echo "[INFO] Running in ${CONTEXT} context..."
echo "[INFO] DragonflyDB + redis-tools installation"

# ============================================================================
# STEP 1: Always install redis-tools (works in all contexts)
# ============================================================================
echo "[INFO] Installing redis-tools (redis-cli)..."
if command -v redis-cli &> /dev/null; then
  echo "[INFO] redis-cli already installed, skipping..."
else
  export DEBIAN_FRONTEND=noninteractive
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends redis-tools

  if command -v redis-cli &> /dev/null; then
    echo "[SUCCESS] redis-tools installed: $(redis-cli --version)"
  else
    echo "[ERROR] redis-tools installation failed"
    exit 1
  fi
fi

# Cleanup apt cache in Docker context
if [[ "${CONTEXT}" == "docker" ]]; then
  echo "[INFO] Cleaning up apt cache (Docker context)..."
  sudo apt-get clean
  sudo rm -rf /var/lib/apt/lists/*
fi

# ============================================================================
# STEP 2: Install DragonflyDB via Docker (VMs only, graceful skip if no Docker)
# ============================================================================

# Only run DragonflyDB on VMs (bare metal or LXC VM)
if [[ "${CONTEXT}" == "docker" ]] || [[ "${CONTEXT}" == "lxc_container" ]]; then
  echo "[INFO] DragonflyDB skipped in ${CONTEXT} context (only runs on VMs)"
  echo "[INFO] redis-tools installed successfully"
  exit 0
fi

# Check if Docker is available (graceful skip, not error)
if ! command -v docker &> /dev/null; then
  echo "[WARNING] Docker is not installed, skipping DragonflyDB"
  echo "[INFO] To install DragonflyDB later, run: mpy_install_350_docker.sh first"
  echo "[INFO] redis-tools installed successfully"
  exit 0
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
  echo "[WARNING] Docker daemon is not running, skipping DragonflyDB"
  echo "[INFO] Start Docker with: sudo systemctl start docker"
  echo "[INFO] redis-tools installed successfully"
  exit 0
fi

# Check if container is already running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "[INFO] DragonflyDB container already running, skipping..."
  docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  exit 0
fi

# Check if container exists but is stopped
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "[INFO] DragonflyDB container exists but is stopped, starting..."
  docker start ${CONTAINER_NAME}
else
  echo "[INFO] Pulling DragonflyDB image..."
  docker pull ${DRAGONFLY_IMAGE}

  echo "[INFO] Starting DragonflyDB container..."
  docker run -d \
    --name ${CONTAINER_NAME} \
    --restart=unless-stopped \
    -p 127.0.0.1:${DRAGONFLY_PORT}:6379 \
    ${DRAGONFLY_IMAGE}
fi

# Wait briefly for container to start
sleep 2

# Verify container is running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "[SUCCESS] DragonflyDB container is running"
  docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
else
  echo "[ERROR] DragonflyDB container failed to start"
  docker logs ${CONTAINER_NAME} 2>&1 | tail -20
  exit 1
fi

# Verify DragonflyDB is accepting connections
echo "[INFO] Verifying DragonflyDB connection..."
if docker exec ${CONTAINER_NAME} redis-cli ping 2>/dev/null | grep -q "PONG"; then
  echo "[SUCCESS] DragonflyDB is accepting connections on 127.0.0.1:${DRAGONFLY_PORT}"
else
  echo "[WARNING] DragonflyDB container running but connection test failed"
  echo "[INFO] It may take a moment to initialize. Test with: redis-cli -h 127.0.0.1 -p ${DRAGONFLY_PORT} ping"
fi

echo "[INFO] Installation complete!"
echo "[INFO] Connect with: redis-cli -h 127.0.0.1 -p ${DRAGONFLY_PORT}"
exit 0
