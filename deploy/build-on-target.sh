#!/usr/bin/env sh
set -eu

# Build and start the stack on the target machine (native x86_64).
# Requires internet on the target for base images and pip packages during build.
#
# Run from project root on the target host:
#   sh deploy/build-on-target.sh

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

cd "$ROOT_DIR"

sh "$ROOT_DIR/deploy/bootstrap-docker-offline.sh" 2>/dev/null || true

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker is not installed." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Error: docker compose plugin is not available." >&2
    exit 1
fi

if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "Error: .env not found." >&2
    exit 1
fi

if [ ! -f /etc/docker/daemon.json ] || ! grep -q registry-mirrors /etc/docker/daemon.json 2>/dev/null; then
    echo "Configuring Docker registry mirrors..."
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<'JSON'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1panel.live",
    "https://dockerpull.org"
  ]
}
JSON
    systemctl restart docker
    sleep 2
fi

echo "Stopping existing stack..."
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

echo "Building application images (native platform)..."
docker compose -f docker-compose.yml build

NGINX_IMAGE="${NGINX_BASE_IMAGE:-nginx:1.27-alpine}"
echo "Pulling nginx image..."
docker pull "$NGINX_IMAGE"
docker tag "$NGINX_IMAGE" ruoyi-ai/nginx:latest

sh "$ROOT_DIR/deploy/fix-volume-perms.sh"

echo "Starting production stack..."
docker compose -f docker-compose.prod.yml up -d

echo ""
docker compose -f docker-compose.prod.yml ps

echo ""
echo "Exporting offline bundle for future zero-download upgrades..."
sh "$ROOT_DIR/deploy/export-offline-bundle.sh"

echo ""
echo "Deployment complete."
echo "  API:  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1')/"
echo "  Docs: /docs"
echo "  Offline bundle: deploy/ruoyi-ai-offline-bundle.tar.gz"
echo "  Offline reload:   sh deploy/install-on-target.sh"
