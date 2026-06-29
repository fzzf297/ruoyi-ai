#!/usr/bin/env sh
set -eu

# Load Docker images on the target (internal network) machine.
# Run after copying deploy/*.tar from the build machine.
# Does not download anything from the internet.

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"

for tar_file in \
    "$DEPLOY_DIR/ruoyi-ai-admin.tar" \
    "$DEPLOY_DIR/ruoyi-ai-agent.tar" \
    "$DEPLOY_DIR/ruoyi-ai-nginx.tar"
do
    if [ ! -f "$tar_file" ]; then
        echo "Error: missing $tar_file" >&2
        exit 1
    fi
done

echo "Loading images (offline)..."
docker load -i "$DEPLOY_DIR/ruoyi-ai-admin.tar"
docker load -i "$DEPLOY_DIR/ruoyi-ai-agent.tar"
docker load -i "$DEPLOY_DIR/ruoyi-ai-nginx.tar"

echo "Loaded images:"
docker images | grep ruoyi-ai || true
