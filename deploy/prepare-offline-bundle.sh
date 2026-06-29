#!/usr/bin/env sh
set -eu

# Build a complete offline bundle on a networked x86_64 build machine.
# The target machine needs NO internet — not even on first deploy.
#
# Bundle includes: Docker static binaries, compose plugin, all images, scripts, .env
#
# Usage:
#   AGENT_LLM_API_KEY=sk-xxxx sh deploy/prepare-offline-bundle.sh
#
# Output:
#   deploy/ruoyi-ai-offline-bundle.tar.gz
#
# Environment:
#   SKIP_BUILD=1          reuse existing deploy/*.tar
#   REFETCH_DOCKER=1      re-download docker static binaries
#   BUILD_PLATFORM        default linux/amd64
#   AGENT_LLM_*           passed to prepare-env.sh

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
BUNDLE_DIR="$DEPLOY_DIR/bundle"

cd "$ROOT_DIR"

echo "==> [1/4] Prepare .env"
sh "$DEPLOY_DIR/prepare-env.sh"

echo "==> [2/4] Build and save application images (build machine, needs internet)"
if [ "${SKIP_BUILD:-0}" = "1" ]; then
    for f in ruoyi-ai-admin.tar ruoyi-ai-agent.tar ruoyi-ai-nginx.tar; do
        if [ ! -f "$DEPLOY_DIR/$f" ]; then
            echo "Error: missing $DEPLOY_DIR/$f" >&2
            exit 1
        fi
    done
    echo "SKIP_BUILD=1, using existing image tar files"
else
    sh "$DEPLOY_DIR/build-images.sh"
fi

echo "==> [3/4] Fetch Docker engine + compose (for target first-time offline install)"
if [ ! -f "$DEPLOY_DIR/docker-static.tgz" ] || [ ! -f "$DEPLOY_DIR/docker-compose-linux-x86_64" ] \
    || [ "${REFETCH_DOCKER:-0}" = "1" ]; then
    sh "$DEPLOY_DIR/fetch-docker-static.sh"
else
    echo "Using existing docker-static.tgz and compose binary"
fi

echo "==> [4/4] Assemble offline bundle"
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR/deploy"

cp "$ROOT_DIR/docker-compose.prod.yml" "$BUNDLE_DIR/"
cp "$ROOT_DIR/.env" "$BUNDLE_DIR/"

for f in ruoyi-ai-admin.tar ruoyi-ai-agent.tar ruoyi-ai-nginx.tar \
    docker-static.tgz docker-compose-linux-x86_64; do
    cp "$DEPLOY_DIR/$f" "$BUNDLE_DIR/deploy/"
done

for script in load-images.sh deploy.sh install-on-target.sh install-from-archive.sh \
    fix-volume-perms.sh backup.sh bootstrap-docker-offline.sh nginx.docker.conf; do
    cp "$DEPLOY_DIR/$script" "$BUNDLE_DIR/deploy/"
done

BUNDLE_ARCHIVE="$DEPLOY_DIR/ruoyi-ai-offline-bundle.tar.gz"
tar -czf "$BUNDLE_ARCHIVE" -C "$DEPLOY_DIR" bundle

echo ""
echo "Offline bundle ready: $BUNDLE_ARCHIVE ($(du -h "$BUNDLE_ARCHIVE" | cut -f1))"
echo ""
echo "Copy to air-gapped target, then run (as root):"
echo "  sh deploy/install-from-archive.sh /path/to/ruoyi-ai-offline-bundle.tar.gz"
echo ""
ADMIN_PASSWORD_LINE="$(grep '^ADMIN_API_DEFAULT_ADMIN_PASSWORD=' "$ROOT_DIR/.env" || true)"
if [ -n "$ADMIN_PASSWORD_LINE" ]; then
    echo "$ADMIN_PASSWORD_LINE"
fi
