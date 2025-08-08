# shell_script_name: {{ shell_script_name }}
# shell_script_username : {{ shell_script_username }}
# Received parameters: {{ params }}
# dev_server_obj.app_base_dir = '{{ params.get('dev_server_obj').app_base_dir }}'

# This is a setup script for Ubuntu 24.04 Server
#
# # Expected ENV Vars
export MPY_USERNAME="${MPY_USERNAME:-$USER}" 
export MPY_APP_BASE_DIR="${MPY_APP_BASE_DIR:-/opt/muppy}"  # "{{ params.get('dev_server_obj').app_base_dir }}"
export IKB_PYTHON_VERSION="${IKB_PYTHON_VERSION:-cpython@3.12.8}"
export IKB_ODOO_VERSION="${IKB_ODOO_VERSION:-18}"
export IKB_DEV_MODE="${IKB_DEV_MODE:-False}"

set -x  # activate verbose mode
export DEBIAN_FRONTEND=noninteractive
sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq install -o Dpkg::Progress-Fancy=0 python-dev-is-python3 \
  libffi-dev liblzma-dev zlib1g-dev libbz2-dev libncurses5-dev libncursesw5-dev xz-utils tk-dev libsasl2-dev \
  libldap2 libldap2-dev libz-dev libbz2-dev libreadline-dev libjpeg-dev libfreetype-dev liblcms2-dev libopenjp2-7 \
  libopenjp2-7-dev libwebp7 libwebp-dev libtiff-dev
sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq install -o Dpkg::Progress-Fancy=0 fontconfig fontconfig-config \
  fonts-dejavu-core libfontconfig1 libfontenc1 libxrender1 x11-common xfonts-75dpi xfonts-base xfonts-encodings \
  xfonts-utils


# wkhtmltppdf
# odoo.sh:
#   - odoo 14 => wkhtmltopdf 0.12.6 (with patched qt)
# For ubuntu 24.04 (noble) , we use jammy version
echo "Current path: $(pwd)"
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_amd64.deb
sudo DEBIAN_FRONTEND=noninteractive dpkg -i wkhtmltox_0.12.6.1-3.jammy_amd64.deb >/dev/null
sudo rm wkhtmltox_0.12.6.1-3.jammy_amd64.deb

#
# Ensure /opt/muppy/tools exists and is in path
#
MAIN_DIR="/opt/$MPY_USERNAME"
TOOLS_DIR="$MAIN_DIR/tools"
SRC_DIR="$MAIN_DIR/src"

# Check and create /opt/muppy if necessary
if [ ! -d "$MAIN_DIR" ]; then
    echo "The directory $MAIN_DIR does not exist. Creating..."
    mkdir -p "$MAIN_DIR"
    chown $MPY_USERNAME:$MPY_USERNAME "$MAIN_DIR"
    chmod 755 "$MAIN_DIR"
else
    echo "The directory $MAIN_DIR already exists."
fi

# Check and create /opt/muppy/tools if necessary
if [ ! -d "$TOOLS_DIR" ]; then
    echo "The directory $TOOLS_DIR does not exist. Creating..."
    mkdir -p "$TOOLS_DIR"
    chown $MPY_USERNAME:$MPY_USERNAME "$TOOLS_DIR"
    chmod 755 "$TOOLS_DIR"
else
    echo "The directory $TOOLS_DIR already exists."
fi
# update PATH with muppy tools/
grep -qxF "export PATH=\"\$PATH:${TOOLS_DIR}\"" ~/.bashrc || echo "export PATH=\"\$PATH:${TOOLS_DIR}\"" >> ~/.bashrc

# Check and create $SRC_DIR if necessary
if [ ! -d "$SRC_DIR" ]; then
    echo "The directory $SRC_DIR does not exist. Creating..."
    mkdir -p "$SRC_DIR"
    chown $MPY_USERNAME:$MPY_USERNAME "$SRC_DIR"
    chmod 755 "$SRC_DIR"
else
    echo "The directory $SRC_DIR already exists."
fi


#
# Install uv
#
# install latest uv in TOOLS_DIR
curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="${TOOLS_DIR}" sh


#
# install python
# 
${TOOLS_DIR}/uv python install $IKB_PYTHON_VERSION
IKB_PYTHON_FILE=$(${TOOLS_DIR}/uv python find $IKB_PYTHON_VERSION)

#
# Install ikb
#
if [ "$IKB_DEV_MODE" = "True" ]; then
    # Install inouk buildit with uv install in dev mode
    cd $SRC_DIR
    git clone https://gitlab.com/inouk/buildit.git
    UV_TOOL_BIN_DIR=$TOOLS_DIR $TOOLS_DIR/uv tool install --editable buildit
    grep -qxF 'export PATH="$HOME/.local/bin:$PATH"' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"

else
    cd $SRC_DIR  # useless
    UV_TOOL_BIN_DIR=$TOOLS_DIR $TOOLS_DIR/uv tool install --python=${IKB_PYTHON_VERSION} git+https://gitlab.com/inouk/buildit.git
fi

#
# To uninstall uv version
#    uv tool uninstall inouk.buildit

# To force exit code
#exit 18

#
# Install latest PostgreSQL client
#
export MPY_PG_VERSION="${MPY_PG_VERSION:-}" 
sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq install -o Dpkg::Progress-Fancy=0 postgresql-common
sudo DEBIAN_FRONTEND=noninteractive /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq update -o Dpkg::Progress-Fancy=0
sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq install -o Dpkg::Progress-Fancy=0 postgresql-client$MPY_PG_VERSION libpq-dev

