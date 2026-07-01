import sqlite3
from typing import Optional

from app.core.errors import NotFoundError
from app.schemas.common import ListResponse
from app.schemas.projects import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.utils import unique_or_conflict


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _out(row: sqlite3.Row) -> ProjectOut:
    return ProjectOut(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        description=row["description"],
        baseUrl=row["base_url"],
        status=row["status"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def get_project(conn: sqlite3.Connection, project_id: int) -> Optional[ProjectOut]:
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _out(row) if row else None


def list_projects(
    conn: sqlite3.Connection, page: int, page_size: int, keyword: str
) -> ListResponse:
    pattern = f"%{keyword.strip()}%"
    where = "WHERE code LIKE ? OR name LIKE ?" if keyword.strip() else ""
    params = (pattern, pattern) if where else ()
    total = conn.execute("SELECT COUNT(*) AS total FROM projects " + where, params).fetchone()[
        "total"
    ]
    rows = conn.execute(
        f"""
        SELECT * FROM projects
        {where}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        params + (page_size, (page - 1) * page_size),
    ).fetchall()
    return ListResponse(
        items=[_out(row) for row in rows], total=total, page=page, pageSize=page_size
    )


def create_project(conn: sqlite3.Connection, payload: ProjectCreate) -> ProjectOut:
    try:
        cursor = conn.execute(
            """
            INSERT INTO projects(code, name, description, base_url, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.code,
                payload.name,
                payload.description,
                payload.baseUrl,
                _enum_value(payload.status),
            ),
        )
    except sqlite3.IntegrityError as exc:
        unique_or_conflict(exc, "Project code already exists")
    return get_project(conn, cursor.lastrowid)


def update_project(conn: sqlite3.Connection, project_id: int, payload: ProjectUpdate) -> ProjectOut:
    existing = get_project(conn, project_id)
    if existing is None:
        raise NotFoundError("Project not found")
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return existing
    columns = []
    params = []
    for field, column in {
        "code": "code",
        "name": "name",
        "description": "description",
        "baseUrl": "base_url",
        "status": "status",
    }.items():
        if field in data:
            value = data[field]
            value = _enum_value(value)
            columns.append(f"{column} = ?")
            params.append(value)
    columns.append("updated_at = CURRENT_TIMESTAMP")
    params.append(project_id)
    try:
        conn.execute(
            "UPDATE projects SET {} WHERE id = ?".format(", ".join(columns)), tuple(params)
        )
    except sqlite3.IntegrityError as exc:
        unique_or_conflict(exc, "Project code already exists")
    return get_project(conn, project_id)


def delete_project(conn: sqlite3.Connection, project_id: int) -> None:
    cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    if cursor.rowcount == 0:
        raise NotFoundError("Project not found")
