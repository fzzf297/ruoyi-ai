#!/usr/bin/env sh
set -eu

# Deploy or update the production stack on the target machine.
# Assumes images are already loaded (see load-images.sh) and .env is configured.

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

cd "$ROOT_DIR"

if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "Error: .env not found. Copy deploy/env.production.example to .env and fill in secrets." >&2
    exit 1
fi

sh "$ROOT_DIR/deploy/fix-volume-perms.sh"

echo "Pulling up production stack..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "Deployment status:"
docker compose -f docker-compose.prod.yml ps
