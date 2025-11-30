#!/usr/bin/env bash
set -euo pipefail

# SCRIPT: mpy_install_350_docker.sh
# LAYER: 3 - Platform-Specific Dev Tools
# PURPOSE: Install Docker CE and Docker Compose from official Docker repository
# USAGE: ./mpy_install_350_docker.sh (uses sudo internally - DO NOT run with sudo)
# ENV VARS:
#   - MPY_USERNAME: System username (default: $USER)
# REQUIREMENTS: Ubuntu 24.04 LTS or later, VM environment only, passwordless sudo
# EXIT CODES:
#   0 - Success (installed or already present, or skipped in container)
#   1 - Missing dependencies or installation failed

# Configuration
MPY_USERNAME="${MPY_USERNAME:-$USER}"

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
echo "[INFO] Docker installation (for VMs only)"

# Docker installation only allowed in bare metal and LXC VMs
# Not allowed in Docker containers or LXC containers
if [[ "${CONTEXT}" == "docker" ]] || [[ "${CONTEXT}" == "lxc_container" ]]; then
  echo "[INFO] Docker installation skipped in ${CONTEXT} context"
  echo "[INFO] Docker should only be installed on VMs (bare metal or LXC VM)"
  echo "[INFO] Current context: ${CONTEXT}"
  exit 0  # Exit with success, not error
fi

# If we're here, we're in bare_metal or lxc_vm (both OK for Docker installation)
if [[ "${CONTEXT}" == "lxc_vm" ]]; then
  echo "[INFO] LXC VM detected - proceeding with Docker installation"
fi

# Check if Docker is already installed
if command -v docker &> /dev/null; then
  DOCKER_VERSION=$(docker --version | grep -oP 'Docker version \K[0-9.]+' || echo "unknown")
  echo "[INFO] Docker ${DOCKER_VERSION} already installed"

  # Check if user is in docker group
  if groups ${MPY_USERNAME} | grep -q '\bdocker\b'; then
    echo "[INFO] User ${MPY_USERNAME} already in docker group"
    echo "[INFO] Skipping installation..."
    exit 0
  else
    echo "[INFO] Docker installed but user not in docker group, adding..."
    # Continue to add user to group
  fi
fi

# Only install if Docker not present
if ! command -v docker &> /dev/null; then
  echo "[INFO] Installing Docker CE from official Docker repository..."

  # Install prerequisites
  export DEBIAN_FRONTEND=noninteractive
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg

  # Add Docker's official GPG key
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc > /dev/null
  sudo chmod a+r /etc/apt/keyrings/docker.asc

  # Add Docker repository to APT sources
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  # Install Docker packages
  sudo apt-get update
  sudo apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin
fi

# Add user to docker group for non-root access
if ! groups ${MPY_USERNAME} | grep -q '\bdocker\b'; then
  echo "[INFO] Adding user ${MPY_USERNAME} to docker group..."
  sudo usermod -aG docker ${MPY_USERNAME}
  echo "[SUCCESS] User ${MPY_USERNAME} added to docker group"
  echo "[INFO] User needs to log out and back in for group changes to take effect"
  echo "[INFO] Or run: newgrp docker"
else
  echo "[INFO] User ${MPY_USERNAME} already in docker group"
fi

# Verify installation
if command -v docker &> /dev/null; then
  DOCKER_VER=$(docker --version)
  echo "[SUCCESS] Docker installed: ${DOCKER_VER}"
else
  echo "[ERROR] Docker installation failed"
  exit 1
fi

# Verify Docker Compose plugin
if docker compose version &> /dev/null; then
  COMPOSE_VER=$(docker compose version)
  echo "[SUCCESS] Docker Compose installed: ${COMPOSE_VER}"
else
  echo "[ERROR] Docker Compose installation failed"
  exit 1
fi

# Verify Docker daemon is running
if sudo systemctl is-active --quiet docker; then
  echo "[SUCCESS] Docker daemon is running"
else
  echo "[WARNING] Docker daemon is not running"
  echo "[INFO] Starting Docker daemon..."
  sudo systemctl start docker
  sudo systemctl enable docker
fi

# No cleanup - this script only runs on bare metal
echo "[INFO] Docker installation complete!"
echo "[INFO] User ${MPY_USERNAME} has been added to docker group"
echo "[INFO] Log out and back in, or run 'newgrp docker' to use docker without sudo"
exit 0
