#!/usr/bin/env bash
set -euo pipefail

# SCRIPT: mpy_install_500_odoo18_deps.sh
# LAYER: 5 - Application-Specific (Odoo 18 Dependencies)
# PURPOSE: Install Odoo 18 development dependencies (Python libs, wkhtmltopdf, uv, Python, ikb)
# USAGE: ./mpy_install_500_odoo18_deps.sh (uses sudo internally - DO NOT run with sudo)
# ENV VARS:
#   - MPY_USERNAME: System username (default: $USER)
#   - MPY_APP_BASE_DIR: Base directory (default: /opt/muppy)
#   - IKB_PYTHON_VERSION: Python version (default: cpython@3.12.8)
#   - IKB_ODOO_VERSION: Odoo major version (default: 18)
#   - IKB_DEV_MODE: Install ikb in dev mode (default: False)
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
echo "[INFO] Odoo 18 dependencies installation"

# Configuration
MPY_USERNAME="${MPY_USERNAME:-$USER}"
MPY_APP_BASE_DIR="${MPY_APP_BASE_DIR:-/opt/muppy}"
TOOLS_DIR="$MPY_APP_BASE_DIR/tools"
SRC_DIR="$MPY_APP_BASE_DIR/src"
IKB_PYTHON_VERSION="${IKB_PYTHON_VERSION:-cpython@3.12.8}"
IKB_ODOO_VERSION="${IKB_ODOO_VERSION:-18}"
IKB_DEV_MODE="${IKB_DEV_MODE:-False}"

# Check if dependencies already installed (idempotency)
if command -v uv &> /dev/null && command -v wkhtmltopdf &> /dev/null; then
  UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
  WKHTMLTOPDF_VERSION=$(wkhtmltopdf --version 2>/dev/null | head -n1 || echo "unknown")
  echo "[INFO] Odoo 18 dependencies already installed:"
  echo "  - uv: ${UV_VERSION}"
  echo "  - wkhtmltopdf: ${WKHTMLTOPDF_VERSION}"
  echo "[INFO] Skipping installation..."
  exit 0
fi

echo "[INFO] Installing Odoo 18 dependencies..."

#
# 1. Install Python development libraries
#
echo "[INFO] Installing Python development libraries..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
  python-dev-is-python3 python3-dev python3-venv \
  libffi-dev liblzma-dev zlib1g-dev libbz2-dev \
  libncurses5-dev libncursesw5-dev xz-utils tk-dev \
  libsasl2-dev libldap2 libldap2-dev libz-dev \
  libreadline-dev \
  libjpeg-dev libfreetype-dev liblcms2-dev \
  libopenjp2-7 libopenjp2-7-dev \
  libwebp7 libwebp-dev libtiff-dev

#
# 2. Install font packages
#
echo "[INFO] Installing font packages..."
sudo apt-get install -y --no-install-recommends \
  fontconfig fontconfig-config fonts-dejavu-core \
  libfontconfig1 libfontenc1 libxrender1 \
  x11-common xfonts-75dpi xfonts-base \
  xfonts-encodings xfonts-utils

#
# 3. Install wkhtmltopdf
#
WKHTMLTOPDF_VERSION="0.12.6.1-3"
WKHTMLTOPDF_DEB="wkhtmltox_${WKHTMLTOPDF_VERSION}.jammy_amd64.deb"
WKHTMLTOPDF_URL="https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_VERSION}/${WKHTMLTOPDF_DEB}"

if ! command -v wkhtmltopdf &> /dev/null; then
  echo "[INFO] Installing wkhtmltopdf ${WKHTMLTOPDF_VERSION}..."
  wget -q $WKHTMLTOPDF_URL
  sudo dpkg -i $WKHTMLTOPDF_DEB 2>/dev/null || true
  rm $WKHTMLTOPDF_DEB
else
  echo "[INFO] wkhtmltopdf already installed, skipping..."
fi

#
# 4. Create directory structure
#
echo "[INFO] Creating /opt/muppy directory structure..."
sudo mkdir -p "$MPY_APP_BASE_DIR" "$TOOLS_DIR" "$SRC_DIR"

# Set ownership if installing for specific user
if [[ "$MPY_USERNAME" != "root" ]] && id -u "$MPY_USERNAME" &>/dev/null; then
  sudo chown -R $MPY_USERNAME:$MPY_USERNAME "$MPY_APP_BASE_DIR"
fi
sudo chmod 755 "$MPY_APP_BASE_DIR" "$TOOLS_DIR" "$SRC_DIR"

#
# 5. Install uv (in /opt/muppy/tools with system-wide symlink)
#
if ! command -v uv &> /dev/null; then
  if [ -f "${TOOLS_DIR}/uv" ]; then
    echo "[INFO] uv found in ${TOOLS_DIR}, creating symlink..."
  else
    echo "[INFO] Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="${TOOLS_DIR}" sh
  fi

  # Create symlink for system-wide access
  echo "[INFO] Creating system-wide symlink for uv..."
  sudo ln -sf ${TOOLS_DIR}/uv /usr/local/bin/uv
else
  echo "[INFO] uv already installed and accessible system-wide, skipping..."
fi

#
# 6. Install Python via uv
#
echo "[INFO] Installing Python ${IKB_PYTHON_VERSION} via uv..."
uv python install $IKB_PYTHON_VERSION || {
  echo "[WARNING] Python installation may have failed or version already installed"
}

#
# 8. Verification
#
echo "[INFO] Verifying installations..."
VERIFICATION_FAILED=false

# Check wkhtmltopdf
if command -v wkhtmltopdf &> /dev/null; then
  WKHTMLTOPDF_VER=$(wkhtmltopdf --version 2>/dev/null | head -n1 || echo "installed")
  echo "[SUCCESS] wkhtmltopdf: ${WKHTMLTOPDF_VER}"
else
  echo "[ERROR] wkhtmltopdf installation failed"
  VERIFICATION_FAILED=true
fi

# Check uv
if command -v uv &> /dev/null; then
  UV_VER=$(uv --version 2>/dev/null || echo "installed")
  echo "[SUCCESS] uv: ${UV_VER}"
else
  echo "[ERROR] uv installation failed"
  VERIFICATION_FAILED=true
fi

# Check Python
PYTHON_PATH=$(uv python find $IKB_PYTHON_VERSION 2>/dev/null || echo "not found")
if [[ "$PYTHON_PATH" != "not found" ]]; then
  echo "[SUCCESS] Python: ${PYTHON_PATH}"
else
  echo "[WARNING] Python ${IKB_PYTHON_VERSION} may not be installed correctly"
fi

if $VERIFICATION_FAILED; then
  echo "[ERROR] Some components failed to install"
  exit 1
fi

#
# 9. Cleanup (Docker context only)
#
if [[ "${CONTEXT}" == "docker" ]]; then
  echo "[INFO] Cleaning up apt cache (Docker context)..."
  sudo apt-get clean
  sudo rm -rf /var/lib/apt/lists/*
fi

echo "[INFO] Odoo 18 dependencies installation complete!"
echo "[INFO] Directory structure:"
echo "  - Base: ${MPY_APP_BASE_DIR}"
echo "  - Tools: ${TOOLS_DIR}"
echo "  - Source: ${SRC_DIR}"
echo "[INFO] uv installed in ${TOOLS_DIR} and symlinked to /usr/local/bin/uv"
echo ""
echo "[NEXT STEP] To install ikb, run WITHOUT sudo:"
echo "  .muppy/scripts/mpy_install_510_ikb.sh"
exit 0
