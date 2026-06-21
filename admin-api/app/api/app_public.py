from fastapi import APIRouter

from app.db.database import get_connection
from app.schemas.common import ListResponse
from app.schemas.interfaces import PublicInterfaceOut
from app.schemas.pages import PageOut
from app.services.public import list_public_interfaces, list_public_pages

router = APIRouter()


@router.get("/projects/{project_code}/pages", response_model=ListResponse[PageOut])
def public_pages(project_code: str) -> ListResponse[PageOut]:
    with get_connection() as conn:
        return list_public_pages(conn, project_code)


@router.get("/projects/{project_code}/interfaces", response_model=ListResponse[PublicInterfaceOut])
def public_interfaces(project_code: str) -> ListResponse[PublicInterfaceOut]:
    with get_connection() as conn:
        return list_public_interfaces(conn, project_code)
