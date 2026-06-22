from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_admin
from app.db.database import get_connection
from app.schemas.auth import AdminUserOut
from app.schemas.common import ListResponse
from app.schemas.projects import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)

router = APIRouter()


@router.get("", response_model=ListResponse[ProjectOut])
def list_project_route(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    keyword: str = "",
    _: AdminUserOut = Depends(get_current_admin),
) -> ListResponse[ProjectOut]:
    with get_connection() as conn:
        return list_projects(conn, page, pageSize, keyword)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project_route(
    payload: ProjectCreate,
    _: AdminUserOut = Depends(get_current_admin),
) -> ProjectOut:
    with get_connection() as conn:
        return create_project(conn, payload)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project_route(project_id: int, _: AdminUserOut = Depends(get_current_admin)) -> ProjectOut:
    with get_connection() as conn:
        project = get_project(conn, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectOut)
def update_project_route(
    project_id: int,
    payload: ProjectUpdate,
    _: AdminUserOut = Depends(get_current_admin),
) -> ProjectOut:
    with get_connection() as conn:
        return update_project(conn, project_id, payload)


@router.delete("/{project_id}")
def delete_project_route(project_id: int, _: AdminUserOut = Depends(get_current_admin)) -> dict:
    with get_connection() as conn:
        delete_project(conn, project_id)
    return {"ok": True}
