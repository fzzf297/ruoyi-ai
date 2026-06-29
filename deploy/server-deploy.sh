#!/usr/bin/env sh
set -eu

# One-shot deploy: sync source to server, build x86 images there, start services.
#
# Usage:
#   DEPLOY_HOST=118.196.83.236 DEPLOY_USER=root DEPLOY_PASSWORD='xxx' \
#     AGENT_LLM_API_KEY=sk-xxxx \
#     sh deploy/server-deploy.sh
#
# Environment variables:
#   DEPLOY_HOST          (required)
#   DEPLOY_USER          (default: root)
#   DEPLOY_PASSWORD      or DEPLOY_SSH_KEY
#   DEPLOY_REMOTE_DIR    (default: /opt/ruoyi-ai)
#   AGENT_LLM_*          passed to prepare-env.sh
#   ADMIN_API_DEFAULT_ADMIN_PASSWORD

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
REMOTE_DIR="${DEPLOY_REMOTE_DIR:-/opt/ruoyi-ai}"

if [ -z "${DEPLOY_HOST:-}" ]; then
    echo "Error: DEPLOY_HOST is required." >&2
    exit 1
fi

ssh_cmd() {
    if [ -n "${DEPLOY_SSH_KEY:-}" ]; then
        ssh -i "$DEPLOY_SSH_KEY" -o StrictHostKeyChecking=no "$@"
    elif [ -n "${DEPLOY_PASSWORD:-}" ]; then
        if ! command -v sshpass >/dev/null 2>&1; then
            echo "Error: sshpass not found." >&2
            exit 1
        fi
        sshpass -p "$DEPLOY_PASSWORD" ssh -o StrictHostKeyChecking=no "$@"
    else
        ssh -o StrictHostKeyChecking=no "$@"
    fi
}

rsync_cmd() {
    if [ -n "${DEPLOY_SSH_KEY:-}" ]; then
        rsync -az --delete -e "ssh -i $DEPLOY_SSH_KEY -o StrictHostKeyChecking=no" "$@"
    elif [ -n "${DEPLOY_PASSWORD:-}" ]; then
        rsync -az --delete -e "sshpass -p '$DEPLOY_PASSWORD' ssh -o StrictHostKeyChecking=no" "$@"
    else
        rsync -az --delete -e "ssh -o StrictHostKeyChecking=no" "$@"
    fi
}

DEPLOY_USER="${DEPLOY_USER:-root}"
REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

echo "==> [1/3] Prepare .env"
sh "$DEPLOY_DIR/prepare-env.sh"

echo "==> [2/3] Sync source to ${REMOTE}:${REMOTE_DIR}"
ssh_cmd "$REMOTE" "mkdir -p '$REMOTE_DIR'"
rsync_cmd \
    --exclude '.git' \
    --exclude 'deploy/*.tar' \
    --exclude 'deploy/bundle' \
    --exclude 'deploy/ruoyi-ai-offline-bundle.tar.gz' \
    --exclude 'backend/*/data' \
    --exclude 'backend/*/.venv' \
    --exclude '**/__pycache__' \
    --exclude '**/.pytest_cache' \
    "$ROOT_DIR/" "${REMOTE}:${REMOTE_DIR}/"

echo "==> [3/3] Build and start on server"
ssh_cmd "$REMOTE" "cd '$REMOTE_DIR' && sh deploy/build-on-target.sh"

ADMIN_PASSWORD_LINE="$(grep '^ADMIN_API_DEFAULT_ADMIN_PASSWORD=' "$ROOT_DIR/.env" || true)"

echo ""
echo "=========================================="
echo "Server deployment complete."
echo "  Host: ${DEPLOY_HOST}"
echo "  API:  http://${DEPLOY_HOST}/"
echo "  Docs: http://${DEPLOY_HOST}/docs"
if [ -n "$ADMIN_PASSWORD_LINE" ]; then
    echo "  ${ADMIN_PASSWORD_LINE}"
fi
echo "=========================================="
