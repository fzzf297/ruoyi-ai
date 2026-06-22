from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_admin
from app.db.database import get_connection
from app.schemas.auth import AdminUserOut
from app.schemas.common import ListResponse, StatusPatch
from app.schemas.pages import PageCreate, PageOut, PageUpdate
from app.schemas.versions import ConfigVersionOut
from app.services.pages import (
    create_page,
    delete_page,
    get_page,
    get_page_version,
    list_page_versions,
    list_pages,
    update_page,
    update_page_status,
)

router = APIRouter()


@router.get("/projects/{project_id}/pages", response_model=ListResponse[PageOut])
def list_pages_route(
    project_id: int,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    keyword: str = "",
    _: AdminUserOut = Depends(get_current_admin),
) -> ListResponse[PageOut]:
    with get_connection() as conn:
        return list_pages(conn, project_id, page, pageSize, keyword, include_disabled=True)


@router.post(
    "/projects/{project_id}/pages", response_model=PageOut, status_code=status.HTTP_201_CREATED
)
def create_page_route(
    project_id: int,
    payload: PageCreate,
    _: AdminUserOut = Depends(get_current_admin),
) -> PageOut:
    with get_connection() as conn:
        return create_page(conn, project_id, payload)


@router.get("/pages/{page_id}", response_model=PageOut)
def get_page_route(page_id: int, _: AdminUserOut = Depends(get_current_admin)) -> PageOut:
    with get_connection() as conn:
        return get_page(conn, page_id)


@router.put("/pages/{page_id}", response_model=PageOut)
def update_page_route(
    page_id: int,
    payload: PageUpdate,
    _: AdminUserOut = Depends(get_current_admin),
) -> PageOut:
    with get_connection() as conn:
        return update_page(conn, page_id, payload)


@router.patch("/pages/{page_id}/status", response_model=PageOut)
def update_page_status_route(
    page_id: int,
    payload: StatusPatch,
    _: AdminUserOut = Depends(get_current_admin),
) -> PageOut:
    with get_connection() as conn:
        return update_page_status(conn, page_id, payload.status)


@router.delete("/pages/{page_id}")
def delete_page_route(page_id: int, _: AdminUserOut = Depends(get_current_admin)) -> dict:
    with get_connection() as conn:
        delete_page(conn, page_id)
    return {"ok": True}


@router.get("/pages/{page_id}/versions", response_model=ListResponse[ConfigVersionOut])
def list_page_versions_route(
    page_id: int,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    _: AdminUserOut = Depends(get_current_admin),
) -> ListResponse[ConfigVersionOut]:
    with get_connection() as conn:
        return list_page_versions(conn, page_id, page, pageSize)


@router.get("/pages/{page_id}/versions/{version}", response_model=ConfigVersionOut)
def get_page_version_route(
    page_id: int,
    version: int,
    _: AdminUserOut = Depends(get_current_admin),
) -> ConfigVersionOut:
    with get_connection() as conn:
        return get_page_version(conn, page_id, version)
