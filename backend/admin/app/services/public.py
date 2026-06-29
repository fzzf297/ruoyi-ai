import json
import sqlite3

from app.core.errors import NotFoundError
from app.schemas.common import ListResponse
from app.schemas.interfaces import InterfaceConfigOut, PublicInterfaceOut
from app.schemas.pages import PageOut
from app.schemas.projects import ProjectOut
from app.schemas.versions import ConfigVersionOut
from app.services.interfaces import _out as interface_out
from app.services.interfaces import get_interface_config
from app.services.pages import _out as page_out
from app.services.projects import _out as project_out
from app.services.utils import parse_json


def list_public_projects(
    conn: sqlite3.Connection, page: int, page_size: int
) -> ListResponse[ProjectOut]:
    where = "WHERE status = 'enabled'"
    total = conn.execute(f"SELECT COUNT(*) AS total FROM projects {where}").fetchone()["total"]
    rows = conn.execute(
        f"""
        SELECT * FROM projects
        {where}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, (page - 1) * page_size),
    ).fetchall()
    return ListResponse(
        items=[project_out(row) for row in rows], total=total, page=page, pageSize=page_size
    )


def _enabled_project(conn: sqlite3.Connection, project_code: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM projects WHERE code = ? AND status = 'enabled'",
        (project_code,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Project not found")
    return row


def get_public_project(conn: sqlite3.Connection, project_code: str) -> ProjectOut:
    return project_out(_enabled_project(conn, project_code))


def get_public_page(conn: sqlite3.Connection, project_code: str, page_code: str) -> PageOut:
    project = _enabled_project(conn, project_code)
    row = conn.execute(
        """
        SELECT * FROM admin_pages
        WHERE project_id = ? AND code = ? AND status = 'enabled'
        """,
        (project["id"], page_code),
    ).fetchone()
    if row is None:
        raise NotFoundError("Page not found")
    return page_out(row)


def _enabled_interface_row(
    conn: sqlite3.Connection, project_code: str, interface_code: str
) -> sqlite3.Row:
    project = _enabled_project(conn, project_code)
    row = conn.execute(
        """
        SELECT i.*, c.parsed_json
        FROM app_interfaces i
        LEFT JOIN interface_configs c ON c.interface_id = i.id
        WHERE i.project_id = ? AND i.code = ? AND i.status = 'enabled'
        """,
        (project["id"], interface_code),
    ).fetchone()
    if row is None:
        raise NotFoundError("Interface not found")
    return row


def get_public_interface(
    conn: sqlite3.Connection, project_code: str, interface_code: str
) -> PublicInterfaceOut:
    row = _enabled_interface_row(conn, project_code, interface_code)
    base = interface_out(row)
    parsed = json.loads(row["parsed_json"]) if row["parsed_json"] else None
    return PublicInterfaceOut(**base.model_dump(), parsedConfig=parsed)


def get_public_interface_config(
    conn: sqlite3.Connection, project_code: str, interface_code: str
) -> InterfaceConfigOut:
    row = _enabled_interface_row(conn, project_code, interface_code)
    return get_interface_config(conn, row["id"])


def list_public_pages(
    conn: sqlite3.Connection, project_code: str, page: int, page_size: int
) -> ListResponse[PageOut]:
    project = _enabled_project(conn, project_code)
    where = "WHERE project_id = ? AND status = 'enabled'"
    params = (project["id"],)
    total = conn.execute(
        f"SELECT COUNT(*) AS total FROM admin_pages {where}", params
    ).fetchone()["total"]
    rows = conn.execute(
        f"""
        SELECT * FROM admin_pages
        {where}
        ORDER BY sort_order ASC, id DESC
        LIMIT ? OFFSET ?
        """,
        params + (page_size, (page - 1) * page_size),
    ).fetchall()
    return ListResponse(
        items=[page_out(row) for row in rows], total=total, page=page, pageSize=page_size
    )


def list_public_interfaces(
    conn: sqlite3.Connection, project_code: str, page: int, page_size: int
) -> ListResponse[PublicInterfaceOut]:
    project = _enabled_project(conn, project_code)
    where = "WHERE i.project_id = ? AND i.status = 'enabled'"
    params = (project["id"],)
    total = conn.execute(
        f"SELECT COUNT(*) AS total FROM app_interfaces i {where}", params
    ).fetchone()["total"]
    rows = conn.execute(
        f"""
        SELECT i.*, c.parsed_json
        FROM app_interfaces i
        LEFT JOIN interface_configs c ON c.interface_id = i.id
        {where}
        ORDER BY i.id DESC
        LIMIT ? OFFSET ?
        """,
        params + (page_size, (page - 1) * page_size),
    ).fetchall()
    items = []
    for row in rows:
        base = interface_out(row)
        parsed = json.loads(row["parsed_json"]) if row["parsed_json"] else None
        items.append(PublicInterfaceOut(**base.model_dump(), parsedConfig=parsed))
    return ListResponse(items=items, total=total, page=page, pageSize=page_size)


def _enabled_page_id(
    conn: sqlite3.Connection, project_code: str, page_code: str
) -> int:
    project = _enabled_project(conn, project_code)
    row = conn.execute(
        "SELECT id FROM admin_pages WHERE project_id = ? AND code = ? AND status = 'enabled'",
        (project["id"], page_code),
    ).fetchone()
    if row is None:
        raise NotFoundError("Page not found")
    return row["id"]


def _version_out(row: sqlite3.Row, entity_id_field: str) -> ConfigVersionOut:
    return ConfigVersionOut(
        id=row["id"],
        entityId=row[entity_id_field],
        version=row["version"],
        action=row["action"],
        snapshot=parse_json(row["snapshot_json"]),
        createdAt=row["created_at"],
    )


def list_public_page_versions(
    conn: sqlite3.Connection, project_code: str, page_code: str, page: int, page_size: int
) -> ListResponse[ConfigVersionOut]:
    page_id = _enabled_page_id(conn, project_code, page_code)
    total = conn.execute(
        "SELECT COUNT(*) AS total FROM admin_page_versions WHERE page_id = ?",
        (page_id,),
    ).fetchone()["total"]
    rows = conn.execute(
        """
        SELECT * FROM admin_page_versions
        WHERE page_id = ?
        ORDER BY version DESC
        LIMIT ? OFFSET ?
        """,
        (page_id, page_size, (page - 1) * page_size),
    ).fetchall()
    return ListResponse(
        items=[_version_out(row, "page_id") for row in rows],
        total=total,
        page=page,
        pageSize=page_size,
    )


def list_public_interface_versions(
    conn: sqlite3.Connection,
    project_code: str,
    interface_code: str,
    page: int,
    page_size: int,
) -> ListResponse[ConfigVersionOut]:
    interface_id = _enabled_interface_row(conn, project_code, interface_code)["id"]
    total = conn.execute(
        "SELECT COUNT(*) AS total FROM app_interface_versions WHERE interface_id = ?",
        (interface_id,),
    ).fetchone()["total"]
    rows = conn.execute(
        """
        SELECT * FROM app_interface_versions
        WHERE interface_id = ?
        ORDER BY version DESC
        LIMIT ? OFFSET ?
        """,
        (interface_id, page_size, (page - 1) * page_size),
    ).fetchall()
    return ListResponse(
        items=[_version_out(row, "interface_id") for row in rows],
        total=total,
        page=page,
        pageSize=page_size,
    )
