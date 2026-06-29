import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

os.environ.setdefault("AGENT_LLM_API_KEY", "test-key")
os.environ.setdefault("AGENT_ADMIN_BASE_URL", "http://localhost:8000")
os.environ.setdefault("AGENT_ADMIN_TIMEOUT", "5")

from app.core.errors import AppError, NotFoundError  # noqa: E402
from app.services.admin_client import AdminClient, build_admin_client  # noqa: E402


def _ok(body: dict) -> httpx.Response:
    return httpx.Response(200, json=body)


def _resp(status: int, detail: str = "err") -> httpx.Response:
    return httpx.Response(status, json={"detail": detail})


PROJECT_BODY = {
    "id": 1,
    "code": "demo",
    "name": "Demo",
    "description": "",
    "status": "enabled",
    "createdAt": "2026-01-01T00:00:00",
    "updatedAt": "2026-01-01T00:00:00",
}

PAGE_BODY = {
    "id": 2,
    "projectId": 1,
    "code": "home",
    "name": "Home",
    "route": "/home",
    "sortOrder": 0,
    "status": "enabled",
    "config": {},
    "createdAt": "2026-01-01T00:00:00",
    "updatedAt": "2026-01-01T00:00:00",
}

INTERFACE_BODY = {
    "id": 3,
    "projectId": 1,
    "code": "api",
    "name": "Api",
    "method": "GET",
    "path": "/api",
    "authMode": "none",
    "status": "enabled",
    "description": "",
    "createdAt": "2026-01-01T00:00:00",
    "updatedAt": "2026-01-01T00:00:00",
    "parsedConfig": None,
}

CONFIG_BODY = {
    "interfaceId": 3,
    "yamlText": "version: 1\n",
    "parsedConfig": {},
    "createdAt": "2026-01-01T00:00:00",
    "updatedAt": "2026-01-01T00:00:00",
}

VERSION_BODY = {
    "id": 10,
    "entityId": 2,
    "version": 1,
    "action": "create",
    "snapshot": {},
    "createdAt": "2026-01-01T00:00:00",
}


def _mock_request(return_value: httpx.Response) -> MagicMock:
    client = MagicMock()
    client.request = AsyncMock(return_value=return_value)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


def _patch_client(response: httpx.Response):
    return patch(
        "app.services.admin_client.httpx.AsyncClient",
        return_value=_mock_request(response),
    )


@pytest.mark.anyio
async def test_list_projects() -> None:
    body = {"items": [PROJECT_BODY], "total": 1, "page": 1, "pageSize": 20}
    with _patch_client(_ok(body)):
        client = AdminClient("http://localhost:8000", 5)
        result = await client.list_projects()
        assert result.total == 1
        assert result.items[0].code == "demo"


@pytest.mark.anyio
async def test_get_project() -> None:
    with _patch_client(_ok(PROJECT_BODY)):
        client = AdminClient("http://localhost:8000", 5)
        result = await client.get_project("demo")
        assert result.code == "demo"


@pytest.mark.anyio
async def test_list_pages() -> None:
    body = {"items": [PAGE_BODY], "total": 1, "page": 1, "pageSize": 20}
    with _patch_client(_ok(body)):
        client = AdminClient("http://localhost:8000", 5)
        result = await client.list_pages("demo")
        assert result.items[0].code == "home"


@pytest.mark.anyio
async def test_get_page() -> None:
    with _patch_client(_ok(PAGE_BODY)):
        client = AdminClient("http://localhost:8000", 5)
        result = await client.get_page("demo", "home")
        assert result.code == "home"


@pytest.mark.anyio
async def test_list_page_versions() -> None:
    body = {"items": [VERSION_BODY], "total": 1, "page": 1, "pageSize": 20}
    with _patch_client(_ok(body)):
        client = AdminClient("http://localhost:8000", 5)
        result = await client.list_page_versions("demo", "home")
        assert result.items[0].action == "create"


@pytest.mark.anyio
async def test_list_interfaces() -> None:
    body = {"items": [INTERFACE_BODY], "total": 1, "page": 1, "pageSize": 20}
    with _patch_client(_ok(body)):
        client = AdminClient("http://localhost:8000", 5)
        result = await client.list_interfaces("demo")
        assert result.items[0].code == "api"


@pytest.mark.anyio
async def test_get_interface() -> None:
    with _patch_client(_ok(INTERFACE_BODY)):
        client = AdminClient("http://localhost:8000", 5)
        result = await client.get_interface("demo", "api")
        assert result.code == "api"
        assert result.parsedConfig is None


@pytest.mark.anyio
async def test_get_interface_config() -> None:
    with _patch_client(_ok(CONFIG_BODY)):
        client = AdminClient("http://localhost:8000", 5)
        result = await client.get_interface_config("demo", "api")
        assert result.interfaceId == 3


@pytest.mark.anyio
async def test_list_interface_versions() -> None:
    body = {"items": [VERSION_BODY], "total": 1, "page": 1, "pageSize": 20}
    with _patch_client(_ok(body)):
        client = AdminClient("http://localhost:8000", 5)
        result = await client.list_interface_versions("demo", "api")
        assert result.items[0].action == "create"


@pytest.mark.anyio
async def test_404_raises_not_found() -> None:
    with _patch_client(_resp(404, "Project not found")):
        client = AdminClient("http://localhost:8000", 5)
        with pytest.raises(NotFoundError) as exc_info:
            await client.get_project("nope")
        assert "Project not found" in exc_info.value.message


@pytest.mark.anyio
async def test_timeout_raises_app_error_504() -> None:
    client = AdminClient("http://localhost:8000", 5)
    mock_instance = MagicMock()
    mock_instance.request = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    with patch("app.services.admin_client.httpx.AsyncClient", return_value=mock_instance):
        with pytest.raises(AppError) as exc_info:
            await client.get_project("demo")
        assert exc_info.value.status_code == 504


@pytest.mark.anyio
async def test_connect_error_raises_app_error_503() -> None:
    client = AdminClient("http://localhost:8000", 5)
    mock_instance = MagicMock()
    mock_instance.request = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    with patch("app.services.admin_client.httpx.AsyncClient", return_value=mock_instance):
        with pytest.raises(AppError) as exc_info:
            await client.get_project("demo")
        assert exc_info.value.status_code == 503


@pytest.mark.anyio
async def test_500_raises_app_error_502() -> None:
    with _patch_client(_resp(500)):
        client = AdminClient("http://localhost:8000", 5)
        with pytest.raises(AppError) as exc_info:
            await client.get_project("demo")
        assert exc_info.value.status_code == 502


def test_build_admin_client_uses_settings() -> None:
    client = build_admin_client()
    assert client._base_url == "http://localhost:8000"
    assert client._timeout == 5
