import json
import sqlite3
from typing import Any, Optional

from app.core.errors import ConflictError, NotFoundError


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def ensure_project_exists(conn: sqlite3.Connection, project_id: int) -> None:
    row = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise NotFoundError("Project not found")


def parse_json(value: Optional[str]) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(value)


def unique_or_conflict(exc: sqlite3.IntegrityError, message: str) -> None:
    if "UNIQUE" in str(exc).upper():
        raise ConflictError(message) from exc
    raise exc
