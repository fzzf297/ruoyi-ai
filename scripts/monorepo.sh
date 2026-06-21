#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ADMIN_DIR="$ROOT_DIR/admin-api"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 1
  }
}

case "${1:-}" in
  admin:dev)
    require_cmd python3
    cd "$ADMIN_DIR"
    python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port "${ADMIN_API_PORT:-8000}"
    ;;
  admin:test)
    require_cmd python3
    cd "$ADMIN_DIR"
    PYTHONPYCACHEPREFIX="$ADMIN_DIR/.pycache" python3 -m pytest
    ;;
  admin:lint)
    require_cmd python3
    cd "$ADMIN_DIR"
    python3 -m ruff check
    ;;
  verify)
    sh "$0" admin:lint
    sh "$0" admin:test
    ;;
  *)
    echo "Usage: $0 {admin:dev|admin:test|admin:lint|verify}" >&2
    exit 1
    ;;
esac
