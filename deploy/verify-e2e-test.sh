#!/usr/bin/env sh
set -eu

# Verify bridge + admin seed + agent execute path on the server.

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
RUOYI_ROOT="${RUOYI_ROOT:-/opt/ruoyi-classic}"
BRIDGE_ENV="$RUOYI_ROOT/.bridge.env"

if [ ! -f "$BRIDGE_ENV" ]; then
    echo "FAIL: bridge env missing at $BRIDGE_ENV" >&2
    exit 1
fi
# shellcheck disable=SC1090
. "$BRIDGE_ENV"

HOST="${E2E_HOST:-127.0.0.1}"
FAIL=0

check() {
    if "$@"; then
        echo "PASS: $*"
    else
        echo "FAIL: $*"
        FAIL=1
    fi
}

echo "=== 1. RuoYi bridge auth ==="
BRIDGE_RESP="$(curl -s -X POST "http://${HOST}:8080/api/agent-bridge/auth" \
    -H "Content-Type: application/json" \
    -d "{\"clientId\":\"${BRIDGE_CLIENT_ID}\",\"clientSecret\":\"${BRIDGE_CLIENT_SECRET}\"}")"
echo "$BRIDGE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('headerName') and d.get('headerValue')" \
    && echo "PASS: bridge returns headerName/headerValue" || { echo "FAIL: bridge auth: $BRIDGE_RESP"; FAIL=1; }

echo ""
echo "=== 2. Admin public API (ruoyi-classic) ==="
check curl -sf "http://${HOST}/api/app/projects/ruoyi-classic/interfaces/user_list" | grep -q user_list

echo ""
echo "=== 3. Agent health ==="
check curl -sf "http://${HOST}/agent/health" | grep -q '"status":"ok"'

echo ""
echo "=== 4. Agent execute_interface (in container) ==="
docker exec ruoyi-ai-agent python3 <<'PY'
import asyncio
import json
import os
import sys

os.environ.setdefault("AGENT_LLM_API_KEY", "test")
os.environ.setdefault("AGENT_ADMIN_BASE_URL", "http://admin:8000")

async def main() -> None:
    from app.services.interface_executor import execute_interface

    result = await execute_interface(
        "ruoyi-classic",
        "user_list",
        {"pageNum": "1"},
    )
    data = result.get("data")
    if not isinstance(data, list):
        raise SystemExit(f"expected list data, got: {result!r}")
    print(json.dumps({"rows": len(data), "sample": data[:1]}, ensure_ascii=False))

asyncio.run(main())
PY
if [ $? -eq 0 ]; then
    echo "PASS: execute_interface user_list"
else
    echo "FAIL: execute_interface user_list"
    FAIL=1
fi

echo ""
echo "=== 5. Agent conversation (SSE) ==="
SESSION_ID="$(curl -s -X POST "http://${HOST}/api/agent/sessions" \
    -H "Content-Type: application/json" \
    -d '{"user_label":"e2e"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['sessionId'])")"
echo "sessionId=$SESSION_ID"

SSE_OUT="$(timeout 90 curl -s -N -X POST "http://${HOST}/api/agent/sessions/${SESSION_ID}/messages" \
    -H "Content-Type: application/json" \
    -d '{"content":"请查询 ruoyi-classic 项目的用户列表，返回前3个用户名"}' 2>&1 | tail -20)"
echo "$SSE_OUT"

if echo "$SSE_OUT" | grep -q 'tool_status'; then
    echo "PASS: agent invoked tools"
else
    echo "WARN: tool_status not seen (LLM may answer without tools)"
fi

if echo "$SSE_OUT" | grep -q '"type": "done"'; then
    echo "PASS: SSE completed"
else
    echo "FAIL: SSE did not complete"
    FAIL=1
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "=========================================="
    echo "E2E verification PASSED"
    echo "Try in Reqable / chat:"
    echo "  POST http://118.196.83.236/api/agent/sessions"
    echo "  POST http://118.196.83.236/api/agent/sessions/{id}/messages"
    echo '  Body: {"content":"查询 ruoyi-classic 用户列表"}'
    echo "=========================================="
else
    echo "E2E verification had failures."
    exit 1
fi
