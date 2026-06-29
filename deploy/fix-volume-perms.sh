#!/usr/bin/env sh
set -eu

# Ensure SQLite data volumes are writable by appuser (uid 999).
# Safe to run before every compose up.

APP_UID="${APP_UID:-999}"

for volume in ruoyi-ai_admin-data ruoyi-ai_agent-data; do
    if docker volume inspect "$volume" >/dev/null 2>&1; then
        docker run --rm -v "${volume}:/data" alpine \
            sh -c "mkdir -p /data && chown -R ${APP_UID}:${APP_UID} /data"
    fi
done
