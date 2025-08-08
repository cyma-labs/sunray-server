#!/bin/bash

# Install Node.js LTS 20 + npm from NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Check install
echo "Node.js version : $(node -v)"
echo "npm version     : $(npm -v)"

# To uninstall
#sudo apt remove --purge nodejs
#sudo rm /etc/apt/sources.list.d/nodesource.list

#
# Install Claude code
#
sudo npm install -g @anthropic-ai/claude-code
