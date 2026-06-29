import logging
from typing import Optional, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import AppError, NotFoundError
from app.schemas.admin_data import (
    ConfigVersionOut,
    InterfaceConfigOut,
    PageOut,
    ProjectOut,
    PublicInterfaceOut,
)
from app.schemas.common import ListResponse

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AdminClient:
    def __init__(self, base_url: str, timeout: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def _request(
        self, path: str, model: type[T], params: Optional[dict] = None
    ) -> T:
        return await self._do_request("GET", path, model, params)

    async def _request_list(
        self, path: str, model: type[T], params: Optional[dict] = None
    ) -> ListResponse[T]:
        resp = await self._do_request_raw("GET", path, params)
        return ListResponse[model].model_validate(resp)  # type: ignore[valid-type]

    async def _do_request(
        self, method: str, path: str, model: type[T], params: Optional[dict]
    ) -> T:
        resp = await self._do_request_raw(method, path, params)
        return model.model_validate(resp)

    async def _do_request_raw(
        self, method: str, path: str, params: Optional[dict]
    ) -> dict:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(method, url, params=params)
        except httpx.TimeoutException as exc:
            logger.warning("admin request timeout: path=%s", path)
            raise AppError("ADMIN_TIMEOUT", status_code=504) from exc
        except httpx.ConnectError as exc:
            logger.warning("admin connect failed: path=%s", path)
            raise AppError("ADMIN_UNREACHABLE", status_code=503) from exc
        except httpx.HTTPError as exc:
            logger.warning("admin http error: path=%s", path)
            raise AppError("ADMIN_UNREACHABLE", status_code=503) from exc

        if response.status_code == 404:
            detail = response.json().get("detail", "Resource not found")
            raise NotFoundError(detail)
        if response.status_code >= 400:
            logger.warning("admin api error: path=%s status=%s", path, response.status_code)
            raise AppError(
                f"ADMIN_API_ERROR: {response.status_code}", status_code=502
            )
        return response.json()

    async def list_projects(self, page: int = 1, page_size: int = 20) -> ListResponse[ProjectOut]:
        return await self._request_list(
            "/api/app/projects", ProjectOut, {"page": page, "pageSize": page_size}
        )

    async def get_project(self, project_code: str) -> ProjectOut:
        return await self._request(f"/api/app/projects/{project_code}", ProjectOut)

    async def list_pages(
        self, project_code: str, page: int = 1, page_size: int = 20
    ) -> ListResponse[PageOut]:
        return await self._request_list(
            f"/api/app/projects/{project_code}/pages",
            PageOut,
            {"page": page, "pageSize": page_size},
        )

    async def get_page(self, project_code: str, page_code: str) -> PageOut:
        return await self._request(
            f"/api/app/projects/{project_code}/pages/{page_code}", PageOut
        )

    async def list_page_versions(
        self, project_code: str, page_code: str, page: int = 1, page_size: int = 20
    ) -> ListResponse[ConfigVersionOut]:
        return await self._request_list(
            f"/api/app/projects/{project_code}/pages/{page_code}/versions",
            ConfigVersionOut,
            {"page": page, "pageSize": page_size},
        )

    async def list_interfaces(
        self, project_code: str, page: int = 1, page_size: int = 20
    ) -> ListResponse[PublicInterfaceOut]:
        return await self._request_list(
            f"/api/app/projects/{project_code}/interfaces",
            PublicInterfaceOut,
            {"page": page, "pageSize": page_size},
        )

    async def get_interface(
        self, project_code: str, interface_code: str
    ) -> PublicInterfaceOut:
        return await self._request(
            f"/api/app/projects/{project_code}/interfaces/{interface_code}",
            PublicInterfaceOut,
        )

    async def get_interface_config(
        self, project_code: str, interface_code: str
    ) -> InterfaceConfigOut:
        return await self._request(
            f"/api/app/projects/{project_code}/interfaces/{interface_code}/config",
            InterfaceConfigOut,
        )

    async def list_interface_versions(
        self,
        project_code: str,
        interface_code: str,
        page: int = 1,
        page_size: int = 20,
    ) -> ListResponse[ConfigVersionOut]:
        return await self._request_list(
            f"/api/app/projects/{project_code}/interfaces/{interface_code}/versions",
            ConfigVersionOut,
            {"page": page, "pageSize": page_size},
        )


def build_admin_client() -> AdminClient:
    return AdminClient(settings.admin_base_url, settings.admin_timeout)


admin_client = build_admin_client()
