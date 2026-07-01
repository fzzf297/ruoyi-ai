#!/usr/bin/env sh
set -eu

# Apply agent admin seed migration and configure DeepSeek on the running stack.
#
# Usage:
#   AGENT_LLM_API_KEY=sk-xxxx sh deploy/seed-agent-admin.sh
#
# On remote server:
#   cd /opt/ruoyi-ai && AGENT_LLM_API_KEY=sk-xxxx sh deploy/seed-agent-admin.sh

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ -z "${AGENT_LLM_API_KEY:-}" ] || [ "$AGENT_LLM_API_KEY" = "change-me" ]; then
    echo "Error: set AGENT_LLM_API_KEY to your DeepSeek API key." >&2
    exit 1
fi

if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "Error: .env not found." >&2
    exit 1
fi

# Update .env LLM settings
if grep -q '^AGENT_LLM_API_KEY=' "$ROOT_DIR/.env"; then
    sed -i.bak "s|^AGENT_LLM_API_KEY=.*|AGENT_LLM_API_KEY=${AGENT_LLM_API_KEY}|" "$ROOT_DIR/.env"
else
    echo "AGENT_LLM_API_KEY=${AGENT_LLM_API_KEY}" >> "$ROOT_DIR/.env"
fi
sed -i.bak 's|^AGENT_LLM_BASE_URL=.*|AGENT_LLM_BASE_URL=https://api.deepseek.com|' "$ROOT_DIR/.env" 2>/dev/null || true
sed -i.bak 's|^AGENT_LLM_MODEL=.*|AGENT_LLM_MODEL=deepseek-chat|' "$ROOT_DIR/.env" 2>/dev/null || true
rm -f "$ROOT_DIR/.env.bak"

COMPOSE_FILES="-f docker-compose.prod.yml"
if [ -f "$ROOT_DIR/deploy/coexist/docker-compose.nginx-host.yml" ] \
    && grep -q host.docker.internal "$ROOT_DIR/deploy/nginx.docker.conf" 2>/dev/null; then
    COMPOSE_FILES="$COMPOSE_FILES -f deploy/coexist/docker-compose.nginx-host.yml"
fi

echo "==> Restart admin to apply DB migration 003_seed_agent_project.sql"
docker compose $COMPOSE_FILES up -d admin
sleep 8

echo "==> Restart agent with DeepSeek config"
docker compose $COMPOSE_FILES up -d agent 2>/dev/null \
    || docker compose $COMPOSE_FILES -f docker-compose.debug.yml --profile ai up -d agent

sleep 5
echo ""
echo "Verify public config:"
curl -s "http://127.0.0.1/api/app/projects/ruoyi-ai-agent/pages" | head -c 400 || true
echo ""
echo ""
curl -s -o /dev/null -w "agent health: %{http_code}\n" http://127.0.0.1/agent/health || true
echo "Done. Admin API: http://<host>/docs  project code: ruoyi-ai-agent"
