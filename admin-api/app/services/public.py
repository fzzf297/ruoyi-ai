import json
import sqlite3

from app.core.errors import NotFoundError
from app.schemas.common import ListResponse
from app.schemas.interfaces import PublicInterfaceOut
from app.services.interfaces import _out as interface_out
from app.services.pages import _out as page_out


def _enabled_project(conn: sqlite3.Connection, project_code: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM projects WHERE code = ? AND status = 'enabled'",
        (project_code,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Project not found")
    return row


def list_public_pages(conn: sqlite3.Connection, project_code: str) -> ListResponse:
    project = _enabled_project(conn, project_code)
    rows = conn.execute(
        """
        SELECT * FROM admin_pages
        WHERE project_id = ? AND status = 'enabled'
        ORDER BY sort_order ASC, id DESC
        """,
        (project["id"],),
    ).fetchall()
    items = [page_out(row) for row in rows]
    return ListResponse(items=items, total=len(items), page=1, pageSize=len(items))


def list_public_interfaces(conn: sqlite3.Connection, project_code: str) -> ListResponse:
    project = _enabled_project(conn, project_code)
    rows = conn.execute(
        """
        SELECT i.*, c.parsed_json
        FROM app_interfaces i
        LEFT JOIN interface_configs c ON c.interface_id = i.id
        WHERE i.project_id = ? AND i.status = 'enabled'
        ORDER BY i.id DESC
        """,
        (project["id"],),
    ).fetchall()
    items = []
    for row in rows:
        base = interface_out(row)
        parsed = json.loads(row["parsed_json"]) if row["parsed_json"] else None
        items.append(PublicInterfaceOut(**base.model_dump(), parsedConfig=parsed))
    return ListResponse(items=items, total=len(items), page=1, pageSize=len(items))
