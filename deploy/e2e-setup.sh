#!/usr/bin/env sh
set -eu

# Full E2E setup on the server: build ruoyi-ai, install RuoYi bridge, verify.
# Run on server: cd /opt/ruoyi-ai && sh deploy/e2e-setup.sh

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

COEXIST="$ROOT_DIR/deploy/coexist"
ENV_BACKUP=""
if [ -f "$ROOT_DIR/.env" ]; then
    ENV_BACKUP="$(mktemp)"
    cp "$ROOT_DIR/.env" "$ENV_BACKUP"
fi

echo "==> [1/6] Build ruoyi-ai images"
docker compose -f docker-compose.yml build admin agent

NGINX_IMAGE="${NGINX_BASE_IMAGE:-nginx:1.27-alpine}"
docker pull "$NGINX_IMAGE" 2>/dev/null || true
docker tag "$NGINX_IMAGE" ruoyi-ai/nginx:latest 2>/dev/null || true

sh "$ROOT_DIR/deploy/fix-volume-perms.sh" 2>/dev/null || true

echo "==> [2/6] Coexist nginx + host gateway"
cp "$COEXIST/nginx.docker.conf" "$ROOT_DIR/deploy/nginx.docker.conf"

echo "==> [3/6] Install RuoYi agent bridge"
sh "$COEXIST/install-agent-bridge.sh"

if [ -n "$ENV_BACKUP" ] && [ -f "$ENV_BACKUP" ]; then
    if grep -q '^AGENT_LLM_API_KEY=change-me' "$ROOT_DIR/.env" 2>/dev/null \
        && grep -qv '^AGENT_LLM_API_KEY=change-me' "$ENV_BACKUP"; then
        OLD_KEY_LINE="$(grep '^AGENT_LLM_API_KEY=' "$ENV_BACKUP" | head -1)"
        sed -i "s|^AGENT_LLM_API_KEY=.*|${OLD_KEY_LINE}|" "$ROOT_DIR/.env"
        echo "Restored AGENT_LLM_API_KEY from pre-setup backup."
    fi
    rm -f "$ENV_BACKUP"
fi

echo "==> [3b] Ensure LLM key in .env (if still placeholder)"
if grep -q '^AGENT_LLM_API_KEY=change-me' "$ROOT_DIR/.env" 2>/dev/null; then
    echo "WARN: AGENT_LLM_API_KEY is still change-me — set a real key for chat tests."
fi

echo "==> [4/6] Start ruoyi-ai stack"
docker compose -f docker-compose.prod.yml -f "$COEXIST/docker-compose.nginx-host.yml" up -d --force-recreate admin agent nginx
sleep 12

echo "==> [5/6] Wait for healthy services"
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1/agent/health >/dev/null \
        && curl -sf http://127.0.0.1/docs >/dev/null; then
        break
    fi
    sleep 2
done

echo "==> [6/6] Run verification"
sh "$ROOT_DIR/deploy/verify-e2e-test.sh"
