import json
import sqlite3

from app.core.errors import NotFoundError
from app.schemas.common import ListResponse
from app.schemas.pages import PageCreate, PageOut, PageUpdate
from app.schemas.versions import ConfigVersionOut
from app.services.utils import ensure_project_exists, parse_json, unique_or_conflict


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _out(row: sqlite3.Row) -> PageOut:
    return PageOut(
        id=row["id"],
        projectId=row["project_id"],
        code=row["code"],
        name=row["name"],
        route=row["route"],
        sortOrder=row["sort_order"],
        status=row["status"],
        config=parse_json(row["config_json"]),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def get_page(conn: sqlite3.Connection, page_id: int) -> PageOut:
    row = conn.execute("SELECT * FROM admin_pages WHERE id = ?", (page_id,)).fetchone()
    if row is None:
        raise NotFoundError("Page not found")
    return _out(row)


def list_pages(
    conn: sqlite3.Connection,
    project_id: int,
    page: int,
    page_size: int,
    keyword: str,
    include_disabled: bool,
) -> ListResponse:
    ensure_project_exists(conn, project_id)
    filters = ["project_id = ?"]
    params = [project_id]
    if not include_disabled:
        filters.append("status = 'enabled'")
    if keyword.strip():
        filters.append("(code LIKE ? OR name LIKE ? OR route LIKE ?)")
        pattern = f"%{keyword.strip()}%"
        params.extend([pattern, pattern, pattern])
    where = "WHERE " + " AND ".join(filters)
    total = conn.execute(
        "SELECT COUNT(*) AS total FROM admin_pages " + where,
        tuple(params),
    ).fetchone()["total"]
    rows = conn.execute(
        f"""
        SELECT * FROM admin_pages
        {where}
        ORDER BY sort_order ASC, id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [page_size, (page - 1) * page_size]),
    ).fetchall()
    return ListResponse(
        items=[_out(row) for row in rows], total=total, page=page, pageSize=page_size
    )


def create_page(conn: sqlite3.Connection, project_id: int, payload: PageCreate) -> PageOut:
    ensure_project_exists(conn, project_id)
    try:
        cursor = conn.execute(
            """
            INSERT INTO admin_pages(project_id, code, name, route, sort_order, status, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                payload.code,
                payload.name,
                payload.route,
                payload.sortOrder,
                _enum_value(payload.status),
                json.dumps(payload.config, ensure_ascii=False, separators=(",", ":")),
            ),
        )
    except sqlite3.IntegrityError as exc:
        unique_or_conflict(exc, "Page code already exists in this project")
    page = get_page(conn, cursor.lastrowid)
    record_page_version(conn, page.id, "create", page)
    return page


def update_page(conn: sqlite3.Connection, page_id: int, payload: PageUpdate) -> PageOut:
    get_page(conn, page_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return get_page(conn, page_id)
    columns = []
    params = []
    mapping = {
        "code": "code",
        "name": "name",
        "route": "route",
        "sortOrder": "sort_order",
        "status": "status",
        "config": "config_json",
    }
    for field, column in mapping.items():
        if field not in data:
            continue
        value = data[field]
        if field == "config":
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            value = _enum_value(value)
        columns.append(f"{column} = ?")
        params.append(value)
    columns.append("updated_at = CURRENT_TIMESTAMP")
    params.append(page_id)
    try:
        conn.execute(
            "UPDATE admin_pages SET {} WHERE id = ?".format(", ".join(columns)), tuple(params)
        )
    except sqlite3.IntegrityError as exc:
        unique_or_conflict(exc, "Page code already exists in this project")
    page = get_page(conn, page_id)
    record_page_version(conn, page.id, "update", page)
    return page


def update_page_status(conn: sqlite3.Connection, page_id: int, status: str) -> PageOut:
    get_page(conn, page_id)
    conn.execute(
        "UPDATE admin_pages SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (_enum_value(status), page_id),
    )
    page = get_page(conn, page_id)
    record_page_version(conn, page.id, "status", page)
    return page


def delete_page(conn: sqlite3.Connection, page_id: int) -> None:
    page = get_page(conn, page_id)
    record_page_version(conn, page.id, "delete", page)
    cursor = conn.execute("DELETE FROM admin_pages WHERE id = ?", (page_id,))
    if cursor.rowcount == 0:
        raise NotFoundError("Page not found")


def record_page_version(
    conn: sqlite3.Connection,
    page_id: int,
    action: str,
    snapshot: PageOut,
) -> None:
    current = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM admin_page_versions WHERE page_id = ?",
        (page_id,),
    ).fetchone()["version"]
    conn.execute(
        """
        INSERT INTO admin_page_versions(page_id, version, action, snapshot_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            page_id,
            int(current) + 1,
            action,
            json.dumps(snapshot.model_dump(), ensure_ascii=False, separators=(",", ":")),
        ),
    )


def _version_out(row: sqlite3.Row) -> ConfigVersionOut:
    return ConfigVersionOut(
        id=row["id"],
        entityId=row["page_id"],
        version=row["version"],
        action=row["action"],
        snapshot=parse_json(row["snapshot_json"]),
        createdAt=row["created_at"],
    )


def list_page_versions(
    conn: sqlite3.Connection,
    page_id: int,
    page: int,
    page_size: int,
) -> ListResponse:
    total = conn.execute(
        "SELECT COUNT(*) AS total FROM admin_page_versions WHERE page_id = ?",
        (page_id,),
    ).fetchone()["total"]
    if total == 0:
        raise NotFoundError("Page version history not found")
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
        items=[_version_out(row) for row in rows],
        total=total,
        page=page,
        pageSize=page_size,
    )


def get_page_version(conn: sqlite3.Connection, page_id: int, version: int) -> ConfigVersionOut:
    row = conn.execute(
        """
        SELECT * FROM admin_page_versions
        WHERE page_id = ? AND version = ?
        """,
        (page_id, version),
    ).fetchone()
    if row is None:
        raise NotFoundError("Page version not found")
    return _version_out(row)
