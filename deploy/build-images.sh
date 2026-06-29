#!/usr/bin/env sh
set -eu

# Build and package Docker images for offline / internal network deployment.
# Run on a machine with internet access and Docker installed.
#
# Output:
#   deploy/ruoyi-ai-admin.tar
#   deploy/ruoyi-ai-agent.tar
#   deploy/ruoyi-ai-nginx.tar

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
NGINX_IMAGE="${NGINX_BASE_IMAGE:-nginx:1.27-alpine}"

cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker not found. Install Docker on this build machine first." >&2
    exit 1
fi

# Target servers are typically linux/amd64; override with BUILD_PLATFORM if needed.
BUILD_PLATFORM="${BUILD_PLATFORM:-linux/amd64}"
export DOCKER_DEFAULT_PLATFORM="$BUILD_PLATFORM"

echo "Building application images for ${BUILD_PLATFORM}..."
docker compose -f docker-compose.yml build

echo "Pulling nginx base image (tagged for offline load)..."
docker pull --platform "$BUILD_PLATFORM" "$NGINX_IMAGE"
docker tag "$NGINX_IMAGE" ruoyi-ai/nginx:latest

echo "Saving images..."
docker save ruoyi-ai/admin:latest > "$DEPLOY_DIR/ruoyi-ai-admin.tar"
docker save ruoyi-ai/agent:latest > "$DEPLOY_DIR/ruoyi-ai-agent.tar"
docker save ruoyi-ai/nginx:latest > "$DEPLOY_DIR/ruoyi-ai-nginx.tar"

for image in ruoyi-ai/admin:latest ruoyi-ai/agent:latest ruoyi-ai/nginx:latest; do
    arch="$(docker image inspect "$image" --format '{{.Architecture}}')"
    if [ "$arch" != "amd64" ]; then
        echo "Error: $image is $arch, expected amd64." >&2
        echo "Build on an x86_64 machine, or: colima start --arch x86_64 (needs qemu)." >&2
        exit 1
    fi
done

echo "Done. Output files:"
ls -lh "$DEPLOY_DIR"/*.tar
