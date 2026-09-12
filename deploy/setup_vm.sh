#!/bin/bash
# Run ONCE on a fresh Ubuntu 22.04 GCE VM, as a user with sudo (e.g. via `gcloud compute ssh`).
# Usage: chmod +x setup_vm.sh && ./setup_vm.sh
set -euo pipefail

echo "=== Updating system ==="
sudo apt-get update -y
sudo apt-get upgrade -y

echo "=== Installing Docker ==="
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"

echo "=== Installing Python 3.11 + Node.js 20 ==="
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -y
sudo apt-get install -y python3.11 python3.11-venv python3-pip
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt-get install -y nodejs

echo "=== Installing Caddy (automatic HTTPS reverse proxy) ==="
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update -y
sudo apt-get install -y caddy

echo "=== Creating service account for the app ==="
sudo useradd -m -s /bin/bash nexus || true
sudo usermod -aG docker nexus

echo ""
echo "=== Base tooling installed. Next steps (see DEPLOY.md): ==="
echo "1. Copy your project into /opt/nexus-x (git clone, or gcloud compute scp)"
echo "2. Run deploy/setup_app.sh to start Neo4j, the backend venv, and build the frontend"
echo "3. Edit /etc/caddy/Caddyfile with your domain and 'sudo systemctl reload caddy'"
