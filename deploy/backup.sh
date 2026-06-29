#!/usr/bin/env sh
set -eu

# Backup SQLite databases from running production containers.
# Run periodically via cron on the target machine.
#
# Example cron entry (daily at 02:00):
#   0 2 * * * /path/to/deploy/backup.sh

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BACKUP_DIR="$ROOT_DIR/backups/$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

echo "Creating online SQLite backups..."

docker compose -f docker-compose.prod.yml exec -T admin python - <<'PY'
import os
import sqlite3

src = "/app/data/admin-api.db"
dst = "/tmp/admin-api.db.backup"

if not os.path.exists(src):
    open(dst, "w").close()
else:
    with sqlite3.connect(src) as conn:
        with sqlite3.connect(dst) as backup_conn:
            conn.backup(backup_conn)
PY

docker compose -f docker-compose.prod.yml cp admin:/tmp/admin-api.db.backup "$BACKUP_DIR/admin-api.db"

docker compose -f docker-compose.prod.yml exec -T agent python - <<'PY'
import os
import sqlite3

src = "/app/data/agent.db"
dst = "/tmp/agent.db.backup"

if not os.path.exists(src):
    open(dst, "w").close()
else:
    with sqlite3.connect(src) as conn:
        with sqlite3.connect(dst) as backup_conn:
            conn.backup(backup_conn)
PY

docker compose -f docker-compose.prod.yml cp agent:/tmp/agent.db.backup "$BACKUP_DIR/agent.db"

echo "Backup saved to: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"
