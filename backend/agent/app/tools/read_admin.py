import json
import logging
import re
from typing import Any, Optional

from langchain_core.tools import tool

from app.services import interface_executor
from app.services.admin_client import admin_client

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


def _scan_placeholders(value: Any, location: str, params: dict[str, set[str]]) -> None:
    if isinstance(value, str):
        for name in _PLACEHOLDER_RE.findall(value):
            if name.startswith("secret."):
                continue
            params.setdefault(name, set()).add(location)
    elif isinstance(value, dict):
        for item in value.values():
            _scan_placeholders(item, location, params)
    elif isinstance(value, list):
        for item in value:
            _scan_placeholders(item, location, params)


def _extract_interface_params(config: dict[str, Any]) -> list[dict[str, Any]]:
    request = config.get("request")
    if not isinstance(request, dict):
        return []
    found: dict[str, set[str]] = {}
    path = request.get("path")
    if isinstance(path, str):
        _scan_placeholders(path, "path", found)
    for location in ("query", "body", "headers"):
        _scan_placeholders(request.get(location), location, found)
    return [
        {"name": name, "locations": sorted(locations)}
        for name, locations in sorted(found.items())
    ]


def _extract_auth_metadata(config: dict[str, Any]) -> tuple[bool, Optional[str]]:
    auth = config.get("auth")
    if not isinstance(auth, dict):
        return False, None
    auth_required = auth.get("useProjectAuth") is True
    interface_code = auth.get("interfaceCode")
    if isinstance(interface_code, str) and interface_code:
        return auth_required, interface_code
    return auth_required, None


def _is_listable_executable_api(config: dict[str, Any], item_method: str) -> bool:
    if config.get("kind") != "api" or config.get("readOnly") is not True:
        return False
    method = item_method
    request = config.get("request")
    if isinstance(request, dict):
        config_method = request.get("method")
        if isinstance(config_method, str):
            method = config_method
    return method in interface_executor.ALLOWED_EXECUTE_METHODS


@tool
async def list_projects(page: int = 1, page_size: int = 20) -> str:
    """List all enabled projects from the admin system.
    Returns project codes, names, descriptions and status.
    Use this when the user asks about available projects or wants an overview.
    """
    result = await admin_client.list_projects(page=page, page_size=page_size)
    logger.info("tool list_projects: total=%s", result.total)
    return json.dumps(
        {
            "items": [
                {
                    "code": p.code,
                    "name": p.name,
                    "description": p.description,
                    "baseUrl": p.baseUrl,
                    "status": p.status,
                }
                for p in result.items
            ],
            "total": result.total,
            "page": result.page,
            "pageSize": result.pageSize,
        },
        ensure_ascii=False,
    )


@tool
async def list_pages(project_code: str, page: int = 1, page_size: int = 20) -> str:
    """List enabled pages within a project from the admin system.
    Returns page codes, names, routes and sort order.
    Use this when the user asks about pages in a specific project.
    """
    result = await admin_client.list_pages(project_code, page=page, page_size=page_size)
    logger.info("tool list_pages: project=%s total=%s", project_code, result.total)
    return json.dumps(
        {
            "projectCode": project_code,
            "items": [
                {
                    "code": p.code,
                    "name": p.name,
                    "route": p.route,
                    "sortOrder": p.sortOrder,
                    "status": p.status,
                }
                for p in result.items
            ],
            "total": result.total,
            "page": result.page,
            "pageSize": result.pageSize,
        },
        ensure_ascii=False,
    )


@tool
async def list_interfaces(project_code: str, page: int = 1, page_size: int = 20) -> str:
    """List enabled API interfaces within a project from the admin system.
    Returns interface codes, names, HTTP methods, paths and parsed configs.
    Use this when the user asks about API interfaces in a specific project.
    """
    result = await admin_client.list_interfaces(
        project_code, page=page, page_size=page_size
    )
    logger.info(
        "tool list_interfaces: project=%s total=%s", project_code, result.total
    )
    return json.dumps(
        {
            "projectCode": project_code,
            "items": [
                {
                    "code": i.code,
                    "name": i.name,
                    "method": i.method,
                    "path": i.path,
                    "authMode": i.authMode,
                    "description": i.description,
                    "parsedConfig": i.parsedConfig,
                }
                for i in result.items
            ],
            "total": result.total,
            "page": result.page,
            "pageSize": result.pageSize,
        },
        ensure_ascii=False,
    )


@tool
async def get_project(project_code: str) -> str:
    """Get detailed information about a specific project by its code.
    Returns project code, name, description, status and timestamps.
    Use this when the user asks about a single specific project.
    """
    result = await admin_client.get_project(project_code)
    logger.info("tool get_project: code=%s", project_code)
    return json.dumps(
        {
            "code": result.code,
            "name": result.name,
            "description": result.description,
            "baseUrl": result.baseUrl,
            "status": result.status,
            "createdAt": result.createdAt,
            "updatedAt": result.updatedAt,
        },
        ensure_ascii=False,
    )


@tool
async def get_page(project_code: str, page_code: str) -> str:
    """Get detailed information about a specific page within a project.
    Returns page code, name, route, sort order, status and config.
    Use this when the user asks about a single specific page.
    """
    result = await admin_client.get_page(project_code, page_code)
    logger.info("tool get_page: project=%s page=%s", project_code, page_code)
    return json.dumps(
        {
            "code": result.code,
            "name": result.name,
            "route": result.route,
            "sortOrder": result.sortOrder,
            "status": result.status,
            "config": result.config,
        },
        ensure_ascii=False,
    )


@tool
async def get_interface(project_code: str, interface_code: str) -> str:
    """Get detailed information about a specific API interface within a project.
    Returns interface code, name, method, path, auth mode, description and parsed config.
    Use this when the user asks about a single specific API interface.
    """
    result = await admin_client.get_interface(project_code, interface_code)
    logger.info(
        "tool get_interface: project=%s interface=%s", project_code, interface_code
    )
    return json.dumps(
        {
            "code": result.code,
            "name": result.name,
            "method": result.method,
            "path": result.path,
            "authMode": result.authMode,
            "description": result.description,
            "parsedConfig": result.parsedConfig,
        },
        ensure_ascii=False,
    )


@tool
async def get_interface_config(project_code: str, interface_code: str) -> str:
    """Get the YAML configuration of a specific API interface.
    Returns the raw YAML text and the parsed config object.
    Use this when the user asks about the config or YAML of a specific interface.
    """
    result = await admin_client.get_interface_config(project_code, interface_code)
    logger.info(
        "tool get_interface_config: project=%s interface=%s",
        project_code, interface_code,
    )
    return json.dumps(
        {
            "interfaceId": result.interfaceId,
            "yamlText": result.yamlText,
            "parsedConfig": result.parsedConfig,
        },
        ensure_ascii=False,
    )


@tool
async def list_page_versions(
    project_code: str, page_code: str, page: int = 1, page_size: int = 20
) -> str:
    """List version history of a specific page within a project.
    Returns version numbers, actions (create/update/delete/status) and timestamps.
    Use this when the user asks about the change history or versions of a page.
    """
    result = await admin_client.list_page_versions(
        project_code, page_code, page=page, page_size=page_size
    )
    logger.info(
        "tool list_page_versions: project=%s page=%s total=%s",
        project_code, page_code, result.total,
    )
    return json.dumps(
        {
            "projectCode": project_code,
            "pageCode": page_code,
            "items": [
                {
                    "version": v.version,
                    "action": v.action,
                    "createdAt": v.createdAt,
                }
                for v in result.items
            ],
            "total": result.total,
            "page": result.page,
            "pageSize": result.pageSize,
        },
        ensure_ascii=False,
    )


@tool
async def list_interface_versions(
    project_code: str, interface_code: str, page: int = 1, page_size: int = 20
) -> str:
    """List version history of a specific API interface within a project.
    Returns version numbers, actions (create/update/delete/config) and timestamps.
    Use this when the user asks about the change history or versions of an interface.
    """
    result = await admin_client.list_interface_versions(
        project_code, interface_code, page=page, page_size=page_size
    )
    logger.info(
        "tool list_interface_versions: project=%s interface=%s total=%s",
        project_code, interface_code, result.total,
    )
    return json.dumps(
        {
            "projectCode": project_code,
            "interfaceCode": interface_code,
            "items": [
                {
                    "version": v.version,
                    "action": v.action,
                    "createdAt": v.createdAt,
                }
                for v in result.items
            ],
            "total": result.total,
            "page": result.page,
            "pageSize": result.pageSize,
        },
        ensure_ascii=False,
    )


@tool
async def list_executable_interfaces(
    project_code: str, page: int = 1, page_size: int = 20
) -> str:
    """List executable read-only business APIs for a project.
    Only includes kind=api, readOnly=true, and request methods GET or POST.
    Returns params (non-secret placeholders), authRequired, and authInterfaceCode per item.
    Use this before execute_interface when the user asks for business data queries.
    """
    items = []
    fetch_page = 1
    fetch_page_size = 100
    while True:
        result = await admin_client.list_interfaces(
            project_code, page=fetch_page, page_size=fetch_page_size
        )
        for item in result.items:
            config = item.parsedConfig or {}
            if _is_listable_executable_api(config, item.method):
                auth_required, auth_interface_code = _extract_auth_metadata(config)
                items.append(
                    {
                        "code": item.code,
                        "name": item.name,
                        "method": item.method,
                        "path": item.path,
                        "description": item.description,
                        "readOnly": True,
                        "params": _extract_interface_params(config),
                        "authRequired": auth_required,
                        "authInterfaceCode": auth_interface_code,
                    }
                )
        if fetch_page * fetch_page_size >= result.total:
            break
        fetch_page += 1
    start = max(page - 1, 0) * page_size
    page_items = items[start : start + page_size]
    logger.info(
        "tool list_executable_interfaces: project=%s total=%s",
        project_code,
        len(items),
    )
    return json.dumps(
        {
            "projectCode": project_code,
            "items": page_items,
            "total": len(items),
            "page": page,
            "pageSize": page_size,
        },
        ensure_ascii=False,
    )


@tool
async def execute_interface(
    project_code: str,
    interface_code: str,
    params: Optional[dict] = None,
) -> str:
    """Execute a configured read-only third-party API interface (kind=api, readOnly=true).
    Use for business data queries only; write interfaces are not supported.
    """
    result = await interface_executor.execute_interface(
        project_code=project_code,
        interface_code=interface_code,
        params=params or {},
    )
    logger.info(
        "tool execute_interface: project=%s interface=%s",
        project_code,
        interface_code,
    )
    return json.dumps(result, ensure_ascii=False)
