#!/usr/bin/env sh
set -eu

# Start minimal stack for low-memory debug: admin + nginx, agent stopped.
#
# Usage:
#   sh deploy/debug-stack.sh          # stop agent, keep admin+nginx
#   sh deploy/debug-stack.sh --with-ai  # start all services

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

sh "$ROOT_DIR/deploy/fix-volume-perms.sh" 2>/dev/null || true

COMPOSE_FILES="-f docker-compose.prod.yml"
if [ -f "$ROOT_DIR/deploy/coexist/docker-compose.nginx-host.yml" ] \
    && grep -q host.docker.internal "$ROOT_DIR/deploy/nginx.docker.conf" 2>/dev/null; then
    COMPOSE_FILES="$COMPOSE_FILES -f deploy/coexist/docker-compose.nginx-host.yml"
fi

if [ "${1:-}" = "--with-ai" ]; then
    echo "Starting full stack (admin + agent + nginx)..."
    docker compose $COMPOSE_FILES -f docker-compose.debug.yml --profile ai up -d
else
    echo "Starting admin + nginx, stopping agent to free memory..."
    docker compose $COMPOSE_FILES up -d admin nginx
    docker compose $COMPOSE_FILES stop agent 2>/dev/null || true
fi

echo ""
docker compose -f docker-compose.prod.yml ps
echo ""
free -h 2>/dev/null || true
echo ""
echo "Freed memory by stopping agent (~80MB). Your new backend can use ~300-500MB."
echo "Frontend: run 'npm run dev' on your laptop, point API to http://<server-ip>/"
