#!/usr/bin/env bash
set -euo pipefail

# SCRIPT: mpy_install_100_sys_minimum.sh
# LAYER: 1 - System Minimum
# PURPOSE: Install system utilities for remote development and administration
# USAGE: ./mpy_install_100_sys_minimum.sh (uses sudo internally - DO NOT run with sudo)
# ENV VARS: None
# REQUIREMENTS: Ubuntu 24.04 LTS or later, passwordless sudo
# EXIT CODES:
#   0 - Success (installed or already present)
#   1 - Missing dependencies or installation failed

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
echo "[INFO] System minimum installation"

# List of system packages to install
SYSTEM_PACKAGES=(
  curl
  wget
  iputils-ping
  htop
  tmux
  vim
  software-properties-common
  ca-certificates
  locales
  less
  unzip
  tar
  sudo
  lsb-release
)

# Check if key packages are already installed (idempotency)
KEY_PACKAGES="curl vim tmux"
ALL_INSTALLED=true
for pkg in $KEY_PACKAGES; do
  if ! command -v $pkg &> /dev/null; then
    ALL_INSTALLED=false
    break
  fi
done

if [[ "$ALL_INSTALLED" == "true" ]]; then
  echo "[INFO] Key system packages already installed, checking for updates..."
fi

echo "[INFO] Installing system packages..."

# Install packages
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends "${SYSTEM_PACKAGES[@]}"

# Configure locale (en_US.UTF-8)
echo "[INFO] Configuring locale (en_US.UTF-8)..."
if ! locale -a | grep -q "en_US.utf8"; then
  sudo locale-gen en_US.UTF-8
  sudo update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
  echo "[SUCCESS] Locale configured: en_US.UTF-8"
else
  echo "[INFO] Locale en_US.UTF-8 already configured"
fi

# Verify key installations
echo "[INFO] Verifying installations..."
MISSING=()
for pkg in $KEY_PACKAGES; do
  if ! command -v $pkg &> /dev/null; then
    MISSING+=($pkg)
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "[ERROR] Installation incomplete. Missing: ${MISSING[*]}"
  exit 1
fi

echo "[SUCCESS] System packages installed:"
echo "  - curl: $(curl --version | head -n1)"
echo "  - wget: $(wget --version | head -n1)"
echo "  - vim: $(vim --version | head -n1)"
echo "  - tmux: $(tmux -V)"
echo "  - htop: $(htop --version | head -n1)"

# Cleanup (only in Docker context to reduce image size)
if [[ "${CONTEXT}" == "docker" ]]; then
  echo "[INFO] Cleaning up apt cache (Docker context)..."
  sudo apt-get clean
  sudo rm -rf /var/lib/apt/lists/*
fi

echo "[INFO] System minimum installation complete!"
exit 0
