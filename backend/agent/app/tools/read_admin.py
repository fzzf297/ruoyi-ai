import json
import logging

from langchain_core.tools import tool

from app.services.admin_client import admin_client

logger = logging.getLogger(__name__)


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
