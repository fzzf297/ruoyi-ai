import json
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("AGENT_LLM_API_KEY", "test-key")
os.environ.setdefault("AGENT_ADMIN_BASE_URL", "http://localhost:8000")

from app.schemas.admin_data import (  # noqa: E402
    ConfigVersionOut,
    InterfaceConfigOut,
    PageOut,
    ProjectOut,
    PublicInterfaceOut,
)
from app.schemas.common import ListResponse  # noqa: E402
from app.tools import read_admin  # noqa: E402
from app.tools.registry import get_tool_names, get_tools  # noqa: E402

PROJECT = ProjectOut(
    id=1, code="demo", name="Demo", description="test",
    baseUrl="http://third-party.local", status="enabled",
    createdAt="2026-01-01T00:00:00", updatedAt="2026-01-01T00:00:00",
)

PAGE = PageOut(
    id=2, projectId=1, code="home", name="Home", route="/home",
    sortOrder=0, status="enabled", config={},
    createdAt="2026-01-01T00:00:00", updatedAt="2026-01-01T00:00:00",
)

INTERFACE = PublicInterfaceOut(
    id=3, projectId=1, code="api", name="Api", method="GET", path="/api",
    authMode="none", status="enabled", description="desc",
    createdAt="2026-01-01T00:00:00", updatedAt="2026-01-01T00:00:00",
    parsedConfig=None,
)


@pytest.mark.anyio
async def test_list_projects_tool() -> None:
    resp = ListResponse(items=[PROJECT], total=1, page=1, pageSize=20)
    with patch.object(read_admin.admin_client, "list_projects", new=AsyncMock(return_value=resp)):
        result = await read_admin.list_projects.coroutine(page=1, page_size=20)
    data = json.loads(result)
    assert data["total"] == 1
    assert data["items"][0]["code"] == "demo"
    assert data["items"][0]["name"] == "Demo"


@pytest.mark.anyio
async def test_list_pages_tool() -> None:
    resp = ListResponse(items=[PAGE], total=1, page=1, pageSize=20)
    with patch.object(read_admin.admin_client, "list_pages", new=AsyncMock(return_value=resp)):
        result = await read_admin.list_pages.coroutine(project_code="demo", page=1, page_size=20)
    data = json.loads(result)
    assert data["projectCode"] == "demo"
    assert data["items"][0]["code"] == "home"
    assert data["items"][0]["route"] == "/home"


@pytest.mark.anyio
async def test_list_interfaces_tool() -> None:
    resp = ListResponse(items=[INTERFACE], total=1, page=1, pageSize=20)
    with patch.object(read_admin.admin_client, "list_interfaces", new=AsyncMock(return_value=resp)):
        result = await read_admin.list_interfaces.coroutine(
            project_code="demo", page=1, page_size=20
        )
    data = json.loads(result)
    assert data["projectCode"] == "demo"
    assert data["items"][0]["code"] == "api"
    assert data["items"][0]["method"] == "GET"
    assert data["items"][0]["parsedConfig"] is None


def test_get_tools_returns_all_registered_tools() -> None:
    tools = get_tools()
    assert len(tools) == 11


def test_get_tool_names() -> None:
    names = get_tool_names()
    assert "list_projects" in names
    assert "list_pages" in names
    assert "list_interfaces" in names
    assert "list_executable_interfaces" in names
    assert "get_project" in names
    assert "get_page" in names
    assert "get_interface" in names
    assert "get_interface_config" in names
    assert "list_page_versions" in names
    assert "list_interface_versions" in names
    assert "execute_interface" in names


def test_tool_docstrings_nonempty() -> None:
    for t in get_tools():
        assert t.description, f"Tool {t.name} has empty description"


@pytest.mark.anyio
async def test_get_project_tool() -> None:
    with patch.object(
        read_admin.admin_client, "get_project", new=AsyncMock(return_value=PROJECT)
    ):
        result = await read_admin.get_project.coroutine(project_code="demo")
    data = json.loads(result)
    assert data["code"] == "demo"
    assert data["name"] == "Demo"
    assert data["baseUrl"] == "http://third-party.local"


@pytest.mark.anyio
async def test_get_page_tool() -> None:
    with patch.object(
        read_admin.admin_client, "get_page", new=AsyncMock(return_value=PAGE)
    ):
        result = await read_admin.get_page.coroutine(project_code="demo", page_code="home")
    data = json.loads(result)
    assert data["code"] == "home"
    assert data["route"] == "/home"


@pytest.mark.anyio
async def test_get_interface_tool() -> None:
    with patch.object(
        read_admin.admin_client, "get_interface", new=AsyncMock(return_value=INTERFACE)
    ):
        result = await read_admin.get_interface.coroutine(
            project_code="demo", interface_code="api"
        )
    data = json.loads(result)
    assert data["code"] == "api"
    assert data["method"] == "GET"


@pytest.mark.anyio
async def test_get_interface_config_tool() -> None:
    config = InterfaceConfigOut(
        interfaceId=3, yamlText="version: 1\n", parsedConfig={},
        createdAt="2026-01-01T00:00:00", updatedAt="2026-01-01T00:00:00",
    )
    with patch.object(
        read_admin.admin_client,
        "get_interface_config",
        new=AsyncMock(return_value=config),
    ):
        result = await read_admin.get_interface_config.coroutine(
            project_code="demo", interface_code="api"
        )
    data = json.loads(result)
    assert data["interfaceId"] == 3
    assert data["yamlText"] == "version: 1\n"


@pytest.mark.anyio
async def test_list_page_versions_tool() -> None:
    version = ConfigVersionOut(
        id=10, entityId=2, version=1, action="create",
        snapshot={}, createdAt="2026-01-01T00:00:00",
    )
    resp = ListResponse(items=[version], total=1, page=1, pageSize=20)
    with patch.object(
        read_admin.admin_client, "list_page_versions", new=AsyncMock(return_value=resp)
    ):
        result = await read_admin.list_page_versions.coroutine(
            project_code="demo", page_code="home"
        )
    data = json.loads(result)
    assert data["pageCode"] == "home"
    assert data["items"][0]["action"] == "create"


@pytest.mark.anyio
async def test_list_interface_versions_tool() -> None:
    version = ConfigVersionOut(
        id=11, entityId=3, version=1, action="create",
        snapshot={}, createdAt="2026-01-01T00:00:00",
    )
    resp = ListResponse(items=[version], total=1, page=1, pageSize=20)
    with patch.object(
        read_admin.admin_client,
        "list_interface_versions",
        new=AsyncMock(return_value=resp),
    ):
        result = await read_admin.list_interface_versions.coroutine(
            project_code="demo", interface_code="api"
        )
    data = json.loads(result)
    assert data["interfaceCode"] == "api"
    assert data["items"][0]["action"] == "create"


@pytest.mark.anyio
async def test_execute_interface_tool() -> None:
    with patch.object(
        read_admin.interface_executor,
        "execute_interface",
        new=AsyncMock(return_value={"data": [{"id": 1}], "projectCode": "demo"}),
    ):
        result = await read_admin.execute_interface.coroutine(
            project_code="demo",
            interface_code="user_list",
            params={"pageNum": "1"},
        )
    data = json.loads(result)
    assert data["data"] == [{"id": 1}]


@pytest.mark.anyio
async def test_list_executable_interfaces_tool() -> None:
    api_iface = PublicInterfaceOut(
        id=4,
        projectId=1,
        code="user_list",
        name="User List",
        method="POST",
        path="/users",
        authMode="none",
        status="enabled",
        description="",
        createdAt="2026-01-01T00:00:00",
        updatedAt="2026-01-01T00:00:00",
        parsedConfig={"kind": "api", "readOnly": True},
    )
    write_iface = PublicInterfaceOut(
        id=6,
        projectId=1,
        code="create_user",
        name="Create User",
        method="POST",
        path="/users",
        authMode="none",
        status="enabled",
        description="",
        createdAt="2026-01-01T00:00:00",
        updatedAt="2026-01-01T00:00:00",
        parsedConfig={"kind": "api", "readOnly": False},
    )
    auth_iface = PublicInterfaceOut(
        id=5,
        projectId=1,
        code="get_token",
        name="Auth",
        method="POST",
        path="/auth",
        authMode="none",
        status="enabled",
        description="",
        createdAt="2026-01-01T00:00:00",
        updatedAt="2026-01-01T00:00:00",
        parsedConfig={"kind": "auth"},
    )
    put_iface = PublicInterfaceOut(
        id=7,
        projectId=1,
        code="update_user",
        name="Update User",
        method="PUT",
        path="/users/1",
        authMode="none",
        status="enabled",
        description="",
        createdAt="2026-01-01T00:00:00",
        updatedAt="2026-01-01T00:00:00",
        parsedConfig={
            "kind": "api",
            "readOnly": True,
            "request": {"method": "PUT", "path": "/users/1"},
        },
    )
    page1 = ListResponse(items=[api_iface, auth_iface], total=201, page=1, pageSize=100)
    page2 = ListResponse(items=[write_iface, put_iface], total=201, page=2, pageSize=100)

    async def list_interfaces(project_code: str, page: int = 1, page_size: int = 20):
        if page == 1:
            return page1
        return page2

    with patch.object(read_admin.admin_client, "list_interfaces", new=list_interfaces):
        result = await read_admin.list_executable_interfaces.coroutine(
            project_code="demo", page=1, page_size=20
        )
    data = json.loads(result)
    assert data["total"] == 1
    item = data["items"][0]
    assert item["code"] == "user_list"
    assert item["params"] == []
    assert item["authRequired"] is False
    assert item["authInterfaceCode"] is None


@pytest.mark.anyio
async def test_list_executable_interfaces_excludes_put_patch_delete() -> None:
    blocked_methods = []
    for index, method in enumerate(("PUT", "PATCH", "DELETE")):
        blocked_methods.append(
            PublicInterfaceOut(
                id=20 + index,
                projectId=1,
                code=f"blocked_{method.lower()}",
                name=f"Blocked {method}",
                method=method,
                path=f"/items/{index}",
                authMode="none",
                status="enabled",
                description="",
                createdAt="2026-01-01T00:00:00",
                updatedAt="2026-01-01T00:00:00",
                parsedConfig={
                    "kind": "api",
                    "readOnly": True,
                    "request": {"method": method, "path": f"/items/{index}"},
                },
            )
        )
    allowed = PublicInterfaceOut(
        id=30,
        projectId=1,
        code="allowed_get",
        name="Allowed GET",
        method="GET",
        path="/items",
        authMode="none",
        status="enabled",
        description="",
        createdAt="2026-01-01T00:00:00",
        updatedAt="2026-01-01T00:00:00",
        parsedConfig={
            "kind": "api",
            "readOnly": True,
            "request": {"method": "GET", "path": "/items"},
        },
    )
    page1 = ListResponse(items=blocked_methods + [allowed], total=1, page=1, pageSize=100)

    async def list_interfaces(project_code: str, page: int = 1, page_size: int = 20):
        return page1

    with patch.object(read_admin.admin_client, "list_interfaces", new=list_interfaces):
        result = await read_admin.list_executable_interfaces.coroutine(
            project_code="demo", page=1, page_size=20
        )
    data = json.loads(result)
    assert data["total"] == 1
    assert data["items"][0]["code"] == "allowed_get"


@pytest.mark.anyio
async def test_list_executable_interfaces_pagination() -> None:
    read_only_apis = []
    for index in range(3):
        read_only_apis.append(
            PublicInterfaceOut(
                id=10 + index,
                projectId=1,
                code=f"api_{index}",
                name=f"API {index}",
                method="GET",
                path=f"/items/{index}",
                authMode="none",
                status="enabled",
                description="",
                createdAt="2026-01-01T00:00:00",
                updatedAt="2026-01-01T00:00:00",
                parsedConfig={"kind": "api", "readOnly": True},
            )
        )
    page1 = ListResponse(items=read_only_apis[:2], total=201, page=1, pageSize=100)
    page2 = ListResponse(items=read_only_apis[2:], total=201, page=2, pageSize=100)

    async def list_interfaces(project_code: str, page: int = 1, page_size: int = 20):
        if page == 1:
            return page1
        if page == 2:
            return page2
        return ListResponse(items=[], total=201, page=page, pageSize=page_size)

    with patch.object(read_admin.admin_client, "list_interfaces", new=list_interfaces):
        page_one = json.loads(
            await read_admin.list_executable_interfaces.coroutine(
                project_code="demo", page=1, page_size=2
            )
        )
        page_two = json.loads(
            await read_admin.list_executable_interfaces.coroutine(
                project_code="demo", page=2, page_size=2
            )
        )

    assert page_one["total"] == 3
    assert [item["code"] for item in page_one["items"]] == ["api_0", "api_1"]
    assert page_two["total"] == 3
    assert [item["code"] for item in page_two["items"]] == ["api_2"]


@pytest.mark.anyio
async def test_list_executable_interfaces_extracts_params_and_auth() -> None:
    api_iface = PublicInterfaceOut(
        id=4,
        projectId=1,
        code="user_detail",
        name="User Detail",
        method="GET",
        path="/users/{userId}",
        authMode="none",
        status="enabled",
        description="",
        createdAt="2026-01-01T00:00:00",
        updatedAt="2026-01-01T00:00:00",
        parsedConfig={
            "kind": "api",
            "readOnly": True,
            "request": {
                "method": "GET",
                "path": "/users/{userId}",
                "query": {"keyword": "{keyword}", "user": "{userId}"},
                "body": {"pageNum": "{pageNum}", "trace": "{traceId}"},
                "headers": {
                    "X-API-Key": "{secret.apiKey}",
                    "X-Trace": "{traceId}",
                },
            },
            "auth": {"useProjectAuth": True, "interfaceCode": "get_token"},
        },
    )
    page1 = ListResponse(items=[api_iface], total=201, page=1, pageSize=100)
    page2 = ListResponse(items=[], total=201, page=2, pageSize=100)

    async def list_interfaces(project_code: str, page: int = 1, page_size: int = 20):
        if page == 1:
            return page1
        return page2

    with patch.object(read_admin.admin_client, "list_interfaces", new=list_interfaces):
        result = await read_admin.list_executable_interfaces.coroutine(
            project_code="demo", page=1, page_size=20
        )
    data = json.loads(result)
    assert data["total"] == 1
    item = data["items"][0]
    assert item["authRequired"] is True
    assert item["authInterfaceCode"] == "get_token"
    params = {entry["name"]: entry["locations"] for entry in item["params"]}
    assert params["userId"] == ["path", "query"]
    assert params["keyword"] == ["query"]
    assert params["pageNum"] == ["body"]
    assert params["traceId"] == ["body", "headers"]
    assert "apiKey" not in params
    assert "secret.apiKey" not in params


def test_extract_interface_params_from_path_only() -> None:
    result = read_admin._extract_interface_params(
        {
            "request": {
                "path": "/users/{userId}/orders/{orderId}",
            }
        }
    )
    assert result == [
        {"name": "orderId", "locations": ["path"]},
        {"name": "userId", "locations": ["path"]},
    ]


def test_extract_interface_params_from_query_body_headers() -> None:
    result = read_admin._extract_interface_params(
        {
            "request": {
                "path": "/items",
                "query": {"keyword": "{keyword}", "status": "{status}"},
                "body": {"pageNum": "{pageNum}"},
                "headers": {"X-Trace": "{traceId}"},
            }
        }
    )
    assert result == [
        {"name": "keyword", "locations": ["query"]},
        {"name": "pageNum", "locations": ["body"]},
        {"name": "status", "locations": ["query"]},
        {"name": "traceId", "locations": ["headers"]},
    ]


def test_extract_interface_params_merges_locations_for_same_name() -> None:
    result = read_admin._extract_interface_params(
        {
            "request": {
                "path": "/users/{userId}",
                "query": {"user": "{userId}"},
                "body": {"user": "{userId}"},
                "headers": {"X-User": "{userId}"},
            }
        }
    )
    assert result == [{"name": "userId", "locations": ["body", "headers", "path", "query"]}]


def test_extract_interface_params_excludes_secret_placeholders() -> None:
    result = read_admin._extract_interface_params(
        {
            "request": {
                "path": "/secure/{resourceId}",
                "query": {"token": "{secret.accessToken}"},
                "body": {"clientId": "{secret.clientId}", "page": "{pageNum}"},
                "headers": {
                    "Authorization": "Bearer {secret.token}",
                    "X-API-Key": "{secret.apiKey}",
                    "X-Request": "{requestId}",
                },
            }
        }
    )
    names = {item["name"] for item in result}
    assert names == {"pageNum", "requestId", "resourceId"}
    for item in result:
        assert item["name"] not in {"apiKey", "accessToken", "clientId", "token"}
        assert not item["name"].startswith("secret.")


def test_extract_interface_params_returns_empty_when_request_missing() -> None:
    assert read_admin._extract_interface_params({}) == []
    assert read_admin._extract_interface_params({"request": "bad"}) == []
