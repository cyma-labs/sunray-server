#!/usr/bin/env bash
set -euo pipefail

# SCRIPT: mpy_install_300_nodejs_dev.sh
# LAYER: 3 - Node.js Development Environment
# PURPOSE: Install Node.js LTS 20.x and npm from NodeSource
# USAGE: ./mpy_install_300_nodejs_dev.sh (uses sudo internally - DO NOT run with sudo)
# ENV VARS:
#   - NODE_VERSION: Node.js major version (default: 20)
# REQUIREMENTS: Ubuntu 24.04 LTS or later, passwordless sudo
# EXIT CODES:
#   0 - Success (installed or already present)
#   1 - Missing dependencies or installation failed

# Configuration
NODE_VERSION="${NODE_VERSION:-20}"

# Detect execution context (Docker vs LXC vs bare metal)
detect_context() {
  if [ -f /.dockerenv ]; then
    echo "docker"
  elif [ -d /dev/lxd ]; then
    echo "lxc"
  else
    echo "bare_metal"
  fi
}

CONTEXT=$(detect_context)
echo "[INFO] Running in ${CONTEXT} context..."
echo "[INFO] Node.js installation (version ${NODE_VERSION}.x LTS)"

# Check if Node.js is already installed
if command -v node &> /dev/null; then
  INSTALLED_VERSION=$(node --version | grep -oP 'v\K\d+' || echo "unknown")
  if [[ "${INSTALLED_VERSION}" == "${NODE_VERSION}" ]]; then
    NODE_FULL=$(node --version)
    NPM_VER=$(npm --version 2>/dev/null || echo "unknown")
    echo "[INFO] Node.js ${NODE_FULL} and npm ${NPM_VER} already installed, skipping..."
    exit 0
  else
    echo "[INFO] Node.js v${INSTALLED_VERSION}.x found, will install version ${NODE_VERSION}.x..."
  fi
fi

echo "[INFO] Installing Node.js ${NODE_VERSION}.x LTS from NodeSource..."

# Install prerequisites
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg

# Add NodeSource repository
curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | sudo bash -

# Install Node.js (npm is included)
sudo apt-get install -y nodejs

# Verify installation
if command -v node &> /dev/null && command -v npm &> /dev/null; then
  NODE_INSTALLED=$(node --version)
  NPM_INSTALLED=$(npm --version)
  echo "[SUCCESS] Node.js ${NODE_INSTALLED} installed"
  echo "[SUCCESS] npm ${NPM_INSTALLED} installed"
else
  echo "[ERROR] Node.js installation failed"
  exit 1
fi

# Cleanup (only in Docker context to reduce image size)
if [[ "${CONTEXT}" == "docker" ]]; then
  echo "[INFO] Cleaning up apt cache (Docker context)..."
  sudo apt-get clean
  sudo rm -rf /var/lib/apt/lists/*
fi

echo "[INFO] Node.js installation complete!"
exit 0
