#!/usr/bin/env sh
set -eu

# Enable nginx coexist config and host.docker.internal for classic RuoYi on :8080.
# Run from ruoyi-ai project root on the server (as root).

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
COEXIST_DIR="$ROOT_DIR/deploy/coexist"

cd "$ROOT_DIR"

cp "$COEXIST_DIR/nginx.docker.conf" "$ROOT_DIR/deploy/nginx.docker.conf"

# Allow nginx container to reach RuoYi on host :8080
if ! grep -q 'host.docker.internal:host-gateway' docker-compose.prod.yml 2>/dev/null; then
    echo "Add to nginx service in docker-compose.prod.yml:"
    echo "  extra_hosts:"
    echo "    - \"host.docker.internal:host-gateway\""
    echo ""
    echo "Or apply overlay: docker compose -f docker-compose.prod.yml -f deploy/coexist/docker-compose.nginx-host.yml"
fi

docker compose -f docker-compose.prod.yml -f "$COEXIST_DIR/docker-compose.nginx-host.yml" up -d nginx

echo "Coexist nginx enabled."
echo "  RuoYi classic → http://<ip>/"
echo "  ruoyi-ai admin docs → http://<ip>/docs"
echo "  ruoyi-ai agent    → http://<ip>/api/agent/"
