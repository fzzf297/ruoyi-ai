#!/usr/bin/env sh
set -eu

# Download Docker static binaries for the target Linux x86_64 host.
# Run on the build machine (with internet). Output is bundled for offline install.
#
# Files:
#   deploy/docker-static.tgz          docker CLI + dockerd + containerd
#   deploy/docker-compose-linux-x86_64  compose v2 plugin binary

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"

DOCKER_VERSION="${DOCKER_STATIC_VERSION:-26.1.4}"
COMPOSE_VERSION="${DOCKER_COMPOSE_VERSION:-2.29.7}"
ARCH="${DOCKER_TARGET_ARCH:-x86_64}"

cd "$DEPLOY_DIR"

echo "Downloading Docker static ${DOCKER_VERSION} (${ARCH})..."
curl -fsSL \
    "https://download.docker.com/linux/static/stable/${ARCH}/docker-${DOCKER_VERSION}.tgz" \
    -o docker-static.tgz

echo "Downloading Docker Compose ${COMPOSE_VERSION}..."
curl -fsSL \
    "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
    -o docker-compose-linux-x86_64
chmod +x docker-compose-linux-x86_64

ls -lh docker-static.tgz docker-compose-linux-x86_64
