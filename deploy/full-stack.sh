#!/usr/bin/env sh
set -eu

# Restore full production stack (admin + agent + nginx).
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
