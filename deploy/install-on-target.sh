#!/usr/bin/env sh
set -eu

# Install the offline bundle on the target machine.
# No internet access required; only docker load + compose up.
#
# Run from the project root on the target host:
#   sh deploy/install-on-target.sh

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

cd "$ROOT_DIR"

sh "$ROOT_DIR/deploy/bootstrap-docker-offline.sh" 2>/dev/null || true

if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker is not installed on this machine." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Error: docker compose plugin is not available." >&2
    exit 1
fi

if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "Error: .env not found. Copy deploy/env.production.example to .env first." >&2
    exit 1
fi

sh "$ROOT_DIR/deploy/load-images.sh"
sh "$ROOT_DIR/deploy/fix-volume-perms.sh"
sh "$ROOT_DIR/deploy/deploy.sh"

echo ""
echo "Services are up. API entry point:"
echo "  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1')/"
echo "  Admin docs: /docs"
echo "  Agent API:  /api/agent/"
