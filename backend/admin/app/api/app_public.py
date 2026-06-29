from fastapi import APIRouter, Query

from app.db.database import get_connection
from app.schemas.common import ListResponse
from app.schemas.interfaces import InterfaceConfigOut, PublicInterfaceOut
from app.schemas.pages import PageOut
from app.schemas.projects import ProjectOut
from app.schemas.versions import ConfigVersionOut
from app.services.public import (
    get_public_interface,
    get_public_interface_config,
    get_public_page,
    get_public_project,
    list_public_interface_versions,
    list_public_interfaces,
    list_public_page_versions,
    list_public_pages,
    list_public_projects,
)

router = APIRouter()


@router.get("/projects", response_model=ListResponse[ProjectOut])
def public_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> ListResponse[ProjectOut]:
    with get_connection() as conn:
        return list_public_projects(conn, page, page_size)


@router.get("/projects/{project_code}", response_model=ProjectOut)
def public_project(project_code: str) -> ProjectOut:
    with get_connection() as conn:
        return get_public_project(conn, project_code)


@router.get("/projects/{project_code}/pages", response_model=ListResponse[PageOut])
def public_pages(
    project_code: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> ListResponse[PageOut]:
    with get_connection() as conn:
        return list_public_pages(conn, project_code, page, page_size)


@router.get("/projects/{project_code}/pages/{page_code}", response_model=PageOut)
def public_page(project_code: str, page_code: str) -> PageOut:
    with get_connection() as conn:
        return get_public_page(conn, project_code, page_code)


@router.get(
    "/projects/{project_code}/pages/{page_code}/versions",
    response_model=ListResponse[ConfigVersionOut],
)
def public_page_versions(
    project_code: str,
    page_code: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> ListResponse[ConfigVersionOut]:
    with get_connection() as conn:
        return list_public_page_versions(conn, project_code, page_code, page, page_size)


@router.get("/projects/{project_code}/interfaces", response_model=ListResponse[PublicInterfaceOut])
def public_interfaces(
    project_code: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> ListResponse[PublicInterfaceOut]:
    with get_connection() as conn:
        return list_public_interfaces(conn, project_code, page, page_size)


@router.get(
    "/projects/{project_code}/interfaces/{interface_code}",
    response_model=PublicInterfaceOut,
)
def public_interface(project_code: str, interface_code: str) -> PublicInterfaceOut:
    with get_connection() as conn:
        return get_public_interface(conn, project_code, interface_code)


@router.get(
    "/projects/{project_code}/interfaces/{interface_code}/config",
    response_model=InterfaceConfigOut,
)
def public_interface_config(project_code: str, interface_code: str) -> InterfaceConfigOut:
    with get_connection() as conn:
        return get_public_interface_config(conn, project_code, interface_code)


@router.get(
    "/projects/{project_code}/interfaces/{interface_code}/versions",
    response_model=ListResponse[ConfigVersionOut],
)
def public_interface_versions(
    project_code: str,
    interface_code: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> ListResponse[ConfigVersionOut]:
    with get_connection() as conn:
        return list_public_interface_versions(
            conn, project_code, interface_code, page, page_size
        )
