# Check Dockerfile_ikb.sh for build and run instructions.
# Ref https://github.com/devcontainers/images/tree/main/src/base-ubuntu
#FROM mcr.microsoft.com/devcontainers/base:ubuntu-20.04

FROM ubuntu:24.04
LABEL author="Cyril MORISSE"
LABEL description="Sunray Server on Ubuntu 24.04, PostgreSQL client from official repo, coder code-server, Odoo required packages"

ARG USERNAME=muppy
ARG USER_UID=1001
ARG USER_GID=$USER_UID
ARG PG_APT_KEY_URL=https://www.postgresql.org/media/keys/ACCC4CF8.asc
ARG PG_APT_REPOSITORY_URL=http://apt.postgresql.org/pub/repos/apt
ARG MPY_REPO_GIT_TOKEN=${MPY_REPO_GIT_TOKEN:-}
ARG BRANCH_NAME=main

ENV DEBIAN_FRONTEND=noninteractive DEBCONF_NONINTERACTIVE_SEEN=true
# Restore man command
RUN apt update && export DEBIAN_FRONTEND=noninteractive && yes | unminimize 2>&1 && apt install -y sudo tini

# We must:
#   - reinstall wget to avoid a pb with certificate
#   - install tzdata with passed TZ="Etc/UTC" to avoid interactive question relates to timezone
#        Ref: https://serverfault.com/questions/949991/how-to-install-tzdata-on-a-ubuntu-docker-image
#RUN TZ="Etc/UTC" DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata
RUN TZ="Etc/UTC" DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata locales \
    && locale-gen fr_FR.utf8 en_US.utf8 C.utf8

# Install system tools and development utilities
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get -y install --no-install-recommends \
    netcat-openbsd htop iputils-ping software-properties-common tmux vim wget curl \
    # Install Python dependencies and related libraries
    && apt-get -y install --no-install-recommends \
    build-essential clang gcc git llvm make \
    python3-dev python3-venv python3-openssl python-is-python3 \
    libffi-dev liblzma-dev libreadline-dev libsqlite3-dev libyaml-dev \
    libxml2-dev libxslt1-dev && \
    # Install development libraries for compression, encryption, and databases
    apt-get -y install --no-install-recommends \
    libbz2-dev libncurses5-dev libncursesw5-dev libsasl2-dev libldap-dev libssl-dev libz-dev zlib1g-dev xz-utils tk-dev && \
    # Install image processing libraries
    apt-get -y install --no-install-recommends \
    libfreetype-dev libjpeg-dev liblcms2-dev libopenjp2-7 libopenjp2-7-dev libtiff-dev libwebp7 libwebp-dev && \
    # Install fonts and graphical rendering dependencies
    apt-get -y install --no-install-recommends \
    fontconfig fontconfig-config fonts-dejavu-core libfontconfig1 libfontenc1 libxrender1 \
    x11-common xfonts-75dpi xfonts-base xfonts-encodings xfonts-utils

#
# Install PostgreSQL from PostgreSQL APT repository
#
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends gnupg ca-certificates && \
    mkdir -p /etc/apt/keyrings && \
    wget -qO /etc/apt/keyrings/postgresql.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc && \
    echo "deb [signed-by=/etc/apt/keyrings/postgresql.asc] http://apt.postgresql.org/pub/repos/apt noble-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postgresql-client libjson-perl libpq-dev

#
# Install code-server inside container
#
RUN curl -fsSL https://code-server.dev/install.sh | sh 

#
# Install wkhtmltopdf
#
ENV WKHTMTOPDF_DEB_FILE=wkhtmltox_0.12.6.1-3.jammy_amd64.deb
ENV WKHTMTOPDF_DEB_URL=https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/$WKHTMTOPDF_DEB_FILE
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    libfontconfig1 libfreetype6 libx11-6 libxext6 libxrender1 libjpeg-turbo8 xfonts-75dpi xfonts-base xfonts-encodings xfonts-utils \
    libxfont2 fontconfig fonts-dejavu-core libssl-dev libffi-dev \
    && wget $WKHTMTOPDF_DEB_URL \
    && dpkg -i $WKHTMTOPDF_DEB_FILE \
    && rm $WKHTMTOPDF_DEB_FILE

# Install others specific: kubectl, helm
#RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
#    && sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
#    && curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash 

#
# Install uv (must be done as root before switching to non-root user)
#
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

#
# Clean up apt cache
#
RUN DEBIAN_FRONTEND=noninteractive apt-get clean && rm -rf /var/lib/apt/lists/*

#
# Creation user muppy
# Ref: https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user
#
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
    # [Optional] Add sudo support. Omit if you don't need to install software after connecting.
    # && apt update && apt install -y sudo \ 
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    # Create muppy work directory
    && sudo mkdir -p -m 0700 /opt/muppy \
    && sudo chown $USERNAME:$USERNAME /opt/muppy

# [Optional] Set the default user. Omit if you want to keep the default as root.
#USER ${USERNAME}:${USERNAME}
USER ${USERNAME}:${USERNAME}
ENV HOME=/home/${USERNAME}
ENV USERNAME=${USERNAME}
ENV USER_UID=${USER_UID}
ENV USER_GID=${USER_GID}

#
# Install ikb
# 
ENV IKB_SRC_DIR=/opt/muppy/ikb-src
RUN mkdir -p $IKB_SRC_DIR \
    && git clone --branch=master https://gitlab.com/inouk/buildit.git $IKB_SRC_DIR/buildit \
    && uv tool install --editable $IKB_SRC_DIR/buildit \
    && sudo ln -sf /home/muppy/.local/bin/ikb /usr/local/bin/ikb

#
# git clone appserver-toctoc
#
WORKDIR /opt/muppy/
RUN rm -rf /opt/muppy/sunray \
    && git clone --branch=${BRANCH_NAME} --depth=1 https://dockerfile:${MPY_REPO_GIT_TOKEN}@gitlab.com/cmorisse/inouk-sunray-server.git /opt/muppy/appserver-sunray

#
# launch buildit
# We copy buildit.jsonc to repo root to support multi repo
WORKDIR /opt/muppy/appserver-sunray
COPY --chown=$USERNAME:$USERNAME .ikb/buildit.jsonc /opt/muppy/appserver-sunray/
RUN ikb init && ikb install 

# Entrypoint management
# See: https://code.visualstudio.com/remote/advancedcontainers/start-processes
#COPY mkrds-entrypoint.sh /usr/local/bin/mkrds-entrypoint.sh
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/muppy/appserver-sunray/bin/sunray-srvr"]
#CMD ["sleep", "infinity"]

EXPOSE 8069/tcp
EXPOSE 8072/tcp
EXPOSE 8765/tcp
