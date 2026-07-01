#!/usr/bin/env sh
set -eu

# Install Agent Bridge controller into classic RuoYi and rebuild the JAR.
# Run on the server as root.
#
# Environment:
#   RUOYI_ROOT          default /opt/ruoyi-classic
#   RUOYI_AI_ROOT       default /opt/ruoyi-ai
#   BRIDGE_CLIENT_ID    default ruoyi-ai-agent
#   BRIDGE_CLIENT_SECRET  generated if unset
#   RUOYI_SERVICE_USER  default admin
#   RUOYI_SERVICE_PASSWORD default admin123

RUOYI_ROOT="${RUOYI_ROOT:-/opt/ruoyi-classic}"
RUOYI_AI_ROOT="${RUOYI_AI_ROOT:-/opt/ruoyi-ai}"
RUOYI_APP="$RUOYI_ROOT/app"
COEXIST_DIR="$RUOYI_AI_ROOT/deploy/coexist"
BRIDGE_SRC="$COEXIST_DIR/ruoyi-agent-bridge/AgentBridgeController.java"
BRIDGE_ENV="$RUOYI_ROOT/.bridge.env"

BRIDGE_CLIENT_ID="${BRIDGE_CLIENT_ID:-ruoyi-ai-agent}"
if [ -z "${BRIDGE_CLIENT_SECRET:-}" ]; then
    if [ -f "$BRIDGE_ENV" ]; then
        # shellcheck disable=SC1090
        . "$BRIDGE_ENV"
    fi
fi
if [ -z "${BRIDGE_CLIENT_SECRET:-}" ]; then
    BRIDGE_CLIENT_SECRET="$(openssl rand -hex 16)"
fi

RUOYI_SERVICE_USER="${RUOYI_SERVICE_USER:-admin}"
RUOYI_SERVICE_PASSWORD="${RUOYI_SERVICE_PASSWORD:-admin123}"

if [ ! -f "$BRIDGE_SRC" ]; then
    echo "Error: missing $BRIDGE_SRC" >&2
    exit 1
fi

echo "==> [1/5] Write bridge credentials"
cat > "$BRIDGE_ENV" <<EOF
BRIDGE_CLIENT_ID=${BRIDGE_CLIENT_ID}
BRIDGE_CLIENT_SECRET=${BRIDGE_CLIENT_SECRET}
RUOYI_SERVICE_USER=${RUOYI_SERVICE_USER}
EOF
chmod 600 "$BRIDGE_ENV"

echo "==> [2/5] Install Java controller"
DEST_DIR="$RUOYI_APP/ruoyi-admin/src/main/java/com/ruoyi/web/controller/agent"
mkdir -p "$DEST_DIR"
cp "$BRIDGE_SRC" "$DEST_DIR/AgentBridgeController.java"

APP_YML="$RUOYI_APP/ruoyi-admin/src/main/resources/application.yml"
if ! grep -q 'agent-bridge:' "$APP_YML" 2>/dev/null; then
    sed -i "/addressEnabled: false/a\\
  agent-bridge:\\
    client-id: ${BRIDGE_CLIENT_ID}\\
    client-secret: ${BRIDGE_CLIENT_SECRET}\\
    service-username: ${RUOYI_SERVICE_USER}\\
    service-password: ${RUOYI_SERVICE_PASSWORD}\\
    session-ttl-seconds: 7200" "$APP_YML"
else
    sed -i "s|client-id:.*|client-id: ${BRIDGE_CLIENT_ID}|" "$APP_YML"
    sed -i "s|client-secret:.*|client-secret: ${BRIDGE_CLIENT_SECRET}|" "$APP_YML"
    sed -i "s|service-username:.*|service-username: ${RUOYI_SERVICE_USER}|" "$APP_YML"
    sed -i "s|service-password:.*|service-password: ${RUOYI_SERVICE_PASSWORD}|" "$APP_YML"
fi

echo "==> [3/5] Build RuoYi (may take several minutes)"
docker stop ruoyi-ai-agent 2>/dev/null || true
cd "$RUOYI_APP"
mvn -q package -DskipTests -pl ruoyi-admin -am

echo "==> [4/5] Restart RuoYi on :8080"
pkill -f 'ruoyi-admin/target/ruoyi-admin.jar' 2>/dev/null || true
sleep 2
if command -v fuser >/dev/null 2>&1; then
    fuser -k 8080/tcp 2>/dev/null || true
    sleep 2
fi
for i in $(seq 1 30); do
    if ! ss -ltn 2>/dev/null | grep -q ':8080 '; then
        break
    fi
    sleep 1
done
if ss -ltn 2>/dev/null | grep -q ':8080 '; then
    echo "Error: port 8080 still in use; cannot start RuoYi with bridge" >&2
    exit 1
fi
nohup java -Xmx256m -Xms128m -jar "$RUOYI_APP/ruoyi-admin/target/ruoyi-admin.jar" \
    --server.port=8080 > /var/log/ruoyi-classic.log 2>&1 &

echo "Waiting for RuoYi..."
for i in $(seq 1 60); do
    if curl -sf -o /dev/null http://127.0.0.1:8080/login 2>/dev/null; then
        echo "RuoYi is up."
        break
    fi
    sleep 2
done

echo "==> [5/5] Sync secrets to ruoyi-ai .env"
SECRETS_JSON="$(BRIDGE_CLIENT_ID="$BRIDGE_CLIENT_ID" BRIDGE_CLIENT_SECRET="$BRIDGE_CLIENT_SECRET" python3 <<'PY'
import json, os
print(json.dumps({
    "ruoyi-classic": {
        "clientId": os.environ["BRIDGE_CLIENT_ID"],
        "clientSecret": os.environ["BRIDGE_CLIENT_SECRET"],
    }
}, ensure_ascii=False))
PY
)"

ENV_FILE="$RUOYI_AI_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    SECRETS_JSON="$SECRETS_JSON" ENV_FILE="$ENV_FILE" python3 <<'PY'
import os
import re
from pathlib import Path

env_path = Path(os.environ["ENV_FILE"])
secrets = os.environ["SECRETS_JSON"]
text = env_path.read_text(encoding="utf-8")
line = "AGENT_PROJECT_SECRETS=" + secrets
if re.search(r"^AGENT_PROJECT_SECRETS=", text, flags=re.M):
    text = re.sub(
        r"^AGENT_PROJECT_SECRETS=.*$",
        line,
        text,
        count=1,
        flags=re.M,
    )
else:
    text = text.rstrip() + "\n" + line + "\n"
env_path.write_text(text, encoding="utf-8")
PY
else
    echo "Error: $ENV_FILE not found" >&2
    exit 1
fi

echo ""
echo "Bridge installed."
echo "  Credentials: $BRIDGE_ENV"
echo "  Test auth: curl -s -X POST http://127.0.0.1:8080/api/agent-bridge/auth -H 'Content-Type: application/json' -d '{\"clientId\":\"${BRIDGE_CLIENT_ID}\",\"clientSecret\":\"${BRIDGE_CLIENT_SECRET}\"}'"
