#!/usr/bin/env bash
set -euo pipefail

# SCRIPT: mpy_install_400_pg_client.sh
# LAYER: 4 - PostgreSQL Client
# PURPOSE: Install PostgreSQL client from official APT repository
# USAGE: ./mpy_install_400_pg_client.sh (uses sudo internally - DO NOT run with sudo)
# ENV VARS:
#   - PG_VERSION: PostgreSQL major version (default: 16)
# REQUIREMENTS: Ubuntu 24.04 LTS or later, passwordless sudo
# EXIT CODES:
#   0 - Success (installed or already present)
#   1 - Missing dependencies or installation failed

# Configuration
PG_VERSION="${PG_VERSION:-16}"

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
echo "[INFO] PostgreSQL client installation (version ${PG_VERSION})"

# Check if PostgreSQL client is already installed
if command -v psql &> /dev/null; then
  INSTALLED_VERSION=$(psql --version | grep -oP 'psql \(PostgreSQL\) \K\d+' || echo "unknown")
  if [[ "${INSTALLED_VERSION}" == "${PG_VERSION}" ]]; then
    echo "[INFO] PostgreSQL client ${PG_VERSION} already installed, skipping..."
    exit 0
  else
    echo "[INFO] PostgreSQL client ${INSTALLED_VERSION} found, will install version ${PG_VERSION}..."
  fi
fi

echo "[INFO] Installing PostgreSQL client ${PG_VERSION}..."

# Install prerequisites
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y --no-install-recommends gnupg ca-certificates wget

# Add PostgreSQL APT repository (only if not already configured)
if [ -f /etc/apt/sources.list.d/pgdg.sources ] || [ -f /etc/apt/sources.list.d/pgdg.list ]; then
  echo "[INFO] PostgreSQL repository already configured, skipping..."
else
  echo "[INFO] Adding PostgreSQL APT repository..."

  # Create directory for GPG keys
  sudo mkdir -p /usr/share/postgresql-common/pgdg

  # Download and install PostgreSQL GPG key
  wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
    gpg --dearmor | sudo tee /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg > /dev/null

  # Determine Ubuntu codename (noble for 24.04)
  UBUNTU_CODENAME=$(lsb_release -cs)

  # Create DEB822 format source file
  sudo tee /etc/apt/sources.list.d/pgdg.sources > /dev/null << EOF
Types: deb
URIs: https://apt.postgresql.org/pub/repos/apt
Suites: ${UBUNTU_CODENAME}-pgdg
Components: main
Signed-By: /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg
EOF

  echo "[INFO] PostgreSQL repository added successfully"
fi

# Install PostgreSQL client
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends postgresql-client-${PG_VERSION} libpq-dev libjson-perl

# Verify installation
if command -v psql &> /dev/null; then
  INSTALLED=$(psql --version)
  echo "[SUCCESS] PostgreSQL client installed: ${INSTALLED}"
else
  echo "[ERROR] PostgreSQL client installation failed"
  exit 1
fi

# Cleanup (only in Docker context to reduce image size)
if [[ "${CONTEXT}" == "docker" ]]; then
  echo "[INFO] Cleaning up apt cache (Docker context)..."
  sudo apt-get clean
  sudo rm -rf /var/lib/apt/lists/*
fi

echo "[INFO] PostgreSQL client installation complete!"
exit 0
