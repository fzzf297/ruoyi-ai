import json
import sqlite3
from typing import Any

import yaml

from app.core.errors import AppError, NotFoundError
from app.models.enums import HttpMethod
from app.schemas.common import ListResponse
from app.schemas.interfaces import (
    InterfaceConfigOut,
    InterfaceCreate,
    InterfaceOut,
    InterfaceUpdate,
)
from app.schemas.versions import ConfigVersionOut
from app.services.utils import ensure_project_exists, parse_json, unique_or_conflict

FORBIDDEN_YAML_KEYS = {"script", "exec", "eval", "shell", "command"}


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _out(row: sqlite3.Row) -> InterfaceOut:
    return InterfaceOut(
        id=row["id"],
        projectId=row["project_id"],
        code=row["code"],
        name=row["name"],
        method=row["method"],
        path=row["path"],
        authMode=row["auth_mode"],
        status=row["status"],
        description=row["description"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def get_interface(conn: sqlite3.Connection, interface_id: int) -> InterfaceOut:
    row = conn.execute("SELECT * FROM app_interfaces WHERE id = ?", (interface_id,)).fetchone()
    if row is None:
        raise NotFoundError("Interface not found")
    return _out(row)


def list_interfaces(
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
        filters.append("(code LIKE ? OR name LIKE ? OR path LIKE ?)")
        pattern = f"%{keyword.strip()}%"
        params.extend([pattern, pattern, pattern])
    where = "WHERE " + " AND ".join(filters)
    total = conn.execute(
        "SELECT COUNT(*) AS total FROM app_interfaces " + where,
        tuple(params),
    ).fetchone()["total"]
    rows = conn.execute(
        f"""
        SELECT * FROM app_interfaces
        {where}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [page_size, (page - 1) * page_size]),
    ).fetchall()
    return ListResponse(
        items=[_out(row) for row in rows], total=total, page=page, pageSize=page_size
    )


def create_interface(
    conn: sqlite3.Connection,
    project_id: int,
    payload: InterfaceCreate,
) -> InterfaceOut:
    ensure_project_exists(conn, project_id)
    try:
        cursor = conn.execute(
            """
            INSERT INTO app_interfaces(
                project_id, code, name, method, path, auth_mode, status, description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                payload.code,
                payload.name,
                _enum_value(payload.method),
                payload.path,
                _enum_value(payload.authMode),
                _enum_value(payload.status),
                payload.description,
            ),
        )
    except sqlite3.IntegrityError as exc:
        unique_or_conflict(exc, "Interface code already exists in this project")
    app_interface = get_interface(conn, cursor.lastrowid)
    record_interface_version(conn, app_interface.id, "create", app_interface)
    return app_interface


def update_interface(
    conn: sqlite3.Connection,
    interface_id: int,
    payload: InterfaceUpdate,
) -> InterfaceOut:
    get_interface(conn, interface_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return get_interface(conn, interface_id)
    columns = []
    params = []
    mapping = {
        "code": "code",
        "name": "name",
        "method": "method",
        "path": "path",
        "authMode": "auth_mode",
        "status": "status",
        "description": "description",
    }
    for field, column in mapping.items():
        if field not in data:
            continue
        value = data[field]
        value = _enum_value(value)
        columns.append(f"{column} = ?")
        params.append(value)
    columns.append("updated_at = CURRENT_TIMESTAMP")
    params.append(interface_id)
    try:
        conn.execute(
            "UPDATE app_interfaces SET {} WHERE id = ?".format(", ".join(columns)),
            tuple(params),
        )
    except sqlite3.IntegrityError as exc:
        unique_or_conflict(exc, "Interface code already exists in this project")
    app_interface = get_interface(conn, interface_id)
    record_interface_version(conn, app_interface.id, "update", app_interface)
    return app_interface


def update_interface_status(
    conn: sqlite3.Connection, interface_id: int, status: str
) -> InterfaceOut:
    get_interface(conn, interface_id)
    conn.execute(
        "UPDATE app_interfaces SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (_enum_value(status), interface_id),
    )
    app_interface = get_interface(conn, interface_id)
    record_interface_version(conn, app_interface.id, "status", app_interface)
    return app_interface


def delete_interface(conn: sqlite3.Connection, interface_id: int) -> None:
    app_interface = get_interface(conn, interface_id)
    record_interface_version(conn, app_interface.id, "delete", app_interface)
    cursor = conn.execute("DELETE FROM app_interfaces WHERE id = ?", (interface_id,))
    if cursor.rowcount == 0:
        raise NotFoundError("Interface not found")


def validate_yaml_config(yaml_text: str) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise AppError(f"Invalid YAML: {exc}", status_code=400) from exc
    if not isinstance(parsed, dict):
        raise AppError("YAML root must be a mapping", status_code=400)
    _reject_forbidden_keys(parsed)
    request = parsed.get("request")
    if not isinstance(request, dict):
        raise AppError("YAML must contain request mapping", status_code=400)
    method = request.get("method")
    path = request.get("path")
    if method not in {item.value for item in HttpMethod}:
        raise AppError(
            "request.method must be one of GET, POST, PUT, PATCH, DELETE", status_code=400
        )
    if not isinstance(path, str) or not path.startswith("/"):
        raise AppError("request.path must start with /", status_code=400)
    _validate_request_mappings(request)
    if "version" not in parsed:
        raise AppError("YAML must contain version", status_code=400)
    kind = parsed.get("kind", "api")
    if kind not in {"api", "auth"}:
        raise AppError("kind must be one of api, auth", status_code=400)
    if kind == "auth":
        response = parsed.get("response")
        if not isinstance(response, dict):
            raise AppError("auth YAML must contain response mapping", status_code=400)
        header_name_path = response.get("headerNamePath")
        header_value_path = response.get("headerValuePath")
        token_path = response.get("tokenPath")
        token_prefix = response.get("tokenPrefix", "")
        if not isinstance(header_name_path, str) or not header_name_path:
            raise AppError("response.headerNamePath is required", status_code=400)
        has_header_value = isinstance(header_value_path, str) and bool(header_value_path)
        has_token = isinstance(token_path, str) and bool(token_path)
        if not has_header_value and not has_token:
            raise AppError(
                "auth YAML must contain response.headerValuePath or response.tokenPath",
                status_code=400,
            )
        if "tokenPrefix" in response and not isinstance(token_prefix, str):
            raise AppError("response.tokenPrefix must be a string", status_code=400)
    if kind == "api":
        read_only = parsed.get("readOnly")
        if not isinstance(read_only, bool):
            raise AppError("api YAML must set readOnly: true or readOnly: false", status_code=400)
        auth = parsed.get("auth")
        if auth is not None:
            if not isinstance(auth, dict):
                raise AppError("auth must be a mapping", status_code=400)
            interface_code = auth.get("interfaceCode")
            if interface_code is not None and (
                not isinstance(interface_code, str) or not interface_code.strip()
            ):
                raise AppError(
                    "auth.interfaceCode must be a non-empty string", status_code=400
                )
    return parsed


def _validate_request_mappings(request: dict[str, Any]) -> None:
    for key in ("query", "body", "headers"):
        if key in request and not isinstance(request[key], dict):
            raise AppError(f"request.{key} must be a mapping", status_code=400)


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in FORBIDDEN_YAML_KEYS:
                raise AppError(f"YAML key '{key}' is not allowed", status_code=400)
            _reject_forbidden_keys(nested)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_keys(item)


def get_interface_config(conn: sqlite3.Connection, interface_id: int) -> InterfaceConfigOut:
    get_interface(conn, interface_id)
    row = conn.execute(
        "SELECT * FROM interface_configs WHERE interface_id = ?",
        (interface_id,),
    ).fetchone()
    if row is None:
        return InterfaceConfigOut(
            interfaceId=interface_id,
            yamlText="",
            parsedConfig={},
            createdAt="",
            updatedAt="",
        )
    return InterfaceConfigOut(
        interfaceId=row["interface_id"],
        yamlText=row["yaml_text"],
        parsedConfig=parse_json(row["parsed_json"]),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def update_interface_config(
    conn: sqlite3.Connection,
    interface_id: int,
    yaml_text: str,
) -> InterfaceConfigOut:
    interface = get_interface(conn, interface_id)
    parsed = validate_yaml_config(yaml_text)
    request = parsed["request"]
    if request["method"] != interface.method or request["path"] != interface.path:
        raise AppError(
            "YAML request.method/path must match the interface definition", status_code=400
        )
    parsed_json = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    existing = conn.execute(
        "SELECT interface_id FROM interface_configs WHERE interface_id = ?",
        (interface_id,),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE interface_configs
            SET yaml_text = ?, parsed_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE interface_id = ?
            """,
            (yaml_text, parsed_json, interface_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO interface_configs(interface_id, yaml_text, parsed_json)
            VALUES (?, ?, ?)
            """,
            (interface_id, yaml_text, parsed_json),
        )
    config = get_interface_config(conn, interface_id)
    record_interface_version(conn, interface.id, "config", interface, config)
    return config


def _interface_snapshot(
    conn: sqlite3.Connection,
    app_interface: InterfaceOut,
    config: InterfaceConfigOut = None,
) -> dict[str, Any]:
    if config is None:
        row = conn.execute(
            "SELECT * FROM interface_configs WHERE interface_id = ?",
            (app_interface.id,),
        ).fetchone()
        config_snapshot = None
        if row is not None:
            config_snapshot = {
                "interfaceId": row["interface_id"],
                "yamlText": row["yaml_text"],
                "parsedConfig": parse_json(row["parsed_json"]),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
    else:
        config_snapshot = config.model_dump()
    return {
        "interface": app_interface.model_dump(),
        "config": config_snapshot,
    }


def record_interface_version(
    conn: sqlite3.Connection,
    interface_id: int,
    action: str,
    app_interface: InterfaceOut,
    config: InterfaceConfigOut = None,
) -> None:
    current = conn.execute(
        """
        SELECT COALESCE(MAX(version), 0) AS version
        FROM app_interface_versions
        WHERE interface_id = ?
        """,
        (interface_id,),
    ).fetchone()["version"]
    conn.execute(
        """
        INSERT INTO app_interface_versions(interface_id, version, action, snapshot_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            interface_id,
            int(current) + 1,
            action,
            json.dumps(
                _interface_snapshot(conn, app_interface, config),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ),
    )


def _version_out(row: sqlite3.Row) -> ConfigVersionOut:
    return ConfigVersionOut(
        id=row["id"],
        entityId=row["interface_id"],
        version=row["version"],
        action=row["action"],
        snapshot=parse_json(row["snapshot_json"]),
        createdAt=row["created_at"],
    )


def list_interface_versions(
    conn: sqlite3.Connection,
    interface_id: int,
    page: int,
    page_size: int,
) -> ListResponse:
    total = conn.execute(
        "SELECT COUNT(*) AS total FROM app_interface_versions WHERE interface_id = ?",
        (interface_id,),
    ).fetchone()["total"]
    if total == 0:
        raise NotFoundError("Interface version history not found")
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
        items=[_version_out(row) for row in rows],
        total=total,
        page=page,
        pageSize=page_size,
    )


def get_interface_version(
    conn: sqlite3.Connection,
    interface_id: int,
    version: int,
) -> ConfigVersionOut:
    row = conn.execute(
        """
        SELECT * FROM app_interface_versions
        WHERE interface_id = ? AND version = ?
        """,
        (interface_id, version),
    ).fetchone()
    if row is None:
        raise NotFoundError("Interface version not found")
    return _version_out(row)
