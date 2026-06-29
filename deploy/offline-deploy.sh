#!/usr/bin/env sh
set -eu

# One-shot offline deployment for air-gapped targets (including first deploy).
#
# Build machine (x86_64 + Docker + internet): builds bundle with Docker engine included.
# Target machine: ZERO network — installs Docker from bundle, docker load, compose up.
#
# Usage:
#   DEPLOY_HOST=10.0.0.5 DEPLOY_USER=root DEPLOY_PASSWORD='secret' \
#     AGENT_LLM_API_KEY=sk-xxxx \
#     sh deploy/offline-deploy.sh
#
# Bundle only (copy via USB to air-gapped target):
#   BUNDLE_ONLY=1 AGENT_LLM_API_KEY=sk-xxxx sh deploy/offline-deploy.sh
#
# On air-gapped target after copying archive:
#   sh deploy/install-from-archive.sh /path/to/ruoyi-ai-offline-bundle.tar.gz

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/opt/ruoyi-ai}"
BUNDLE_DIR="$DEPLOY_DIR/bundle"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    sed -n '2,18p' "$0"
    exit 0
fi

if [ -z "${DEPLOY_HOST:-}" ] && [ "${BUNDLE_ONLY:-0}" != "1" ]; then
    echo "Error: DEPLOY_HOST is required (or set BUNDLE_ONLY=1)." >&2
    exit 1
fi

ssh_cmd() {
    if [ -n "${DEPLOY_SSH_KEY:-}" ]; then
        ssh -i "$DEPLOY_SSH_KEY" -o StrictHostKeyChecking=no "$@"
    elif [ -n "${DEPLOY_PASSWORD:-}" ]; then
        command -v sshpass >/dev/null 2>&1 || { echo "Error: sshpass not found." >&2; exit 1; }
        sshpass -p "$DEPLOY_PASSWORD" ssh -o StrictHostKeyChecking=no "$@"
    else
        ssh -o StrictHostKeyChecking=no "$@"
    fi
}

rsync_cmd() {
    if [ -n "${DEPLOY_SSH_KEY:-}" ]; then
        rsync -az -e "ssh -i $DEPLOY_SSH_KEY -o StrictHostKeyChecking=no" "$@"
    elif [ -n "${DEPLOY_PASSWORD:-}" ]; then
        rsync -az -e "sshpass -p '$DEPLOY_PASSWORD' ssh -o StrictHostKeyChecking=no" "$@"
    else
        rsync -az -e "ssh -o StrictHostKeyChecking=no" "$@"
    fi
}

sh "$DEPLOY_DIR/prepare-offline-bundle.sh"
ADMIN_PASSWORD_LINE="$(grep '^ADMIN_API_DEFAULT_ADMIN_PASSWORD=' "$ROOT_DIR/.env" || true)"
BUNDLE_ARCHIVE="$DEPLOY_DIR/ruoyi-ai-offline-bundle.tar.gz"

if [ "${BUNDLE_ONLY:-0}" = "1" ]; then
    echo "Copy $BUNDLE_ARCHIVE to target, then:"
    echo "  sh deploy/install-from-archive.sh ruoyi-ai-offline-bundle.tar.gz"
    exit 0
fi

DEPLOY_USER="${DEPLOY_USER:-root}"
REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

echo "==> Transfer archive to ${REMOTE}..."
ssh_cmd "$REMOTE" "mkdir -p '$REMOTE_DIR'"
rsync_cmd "$BUNDLE_ARCHIVE" "${REMOTE}:${REMOTE_DIR}/"

echo "==> Install on target (offline, first deploy supported)..."
ssh_cmd "$REMOTE" "sh -s" <<EOF
set -eu
cd '$REMOTE_DIR'
if [ -f deploy/install-from-archive.sh ]; then
    sh deploy/install-from-archive.sh ruoyi-ai-offline-bundle.tar.gz '$REMOTE_DIR'
else
    tar -xzf ruoyi-ai-offline-bundle.tar.gz -C /tmp
    cp -a /tmp/bundle/. '$REMOTE_DIR/'
    cd '$REMOTE_DIR' && sh deploy/install-on-target.sh
fi
EOF

echo ""
echo "=========================================="
echo "Offline deployment complete (zero network on target)."
echo "  Host: ${DEPLOY_HOST}"
echo "  API:  http://${DEPLOY_HOST}/"
echo "  Docs: http://${DEPLOY_HOST}/docs"
if [ -n "$ADMIN_PASSWORD_LINE" ]; then
    echo "  ${ADMIN_PASSWORD_LINE}"
fi
echo "=========================================="
