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
    id=1, code="demo", name="Demo", description="test", status="enabled",
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


def test_get_tools_returns_three() -> None:
    tools = get_tools()
    assert len(tools) == 9


def test_get_tool_names() -> None:
    names = get_tool_names()
    assert "list_projects" in names
    assert "list_pages" in names
    assert "list_interfaces" in names
    assert "get_project" in names
    assert "get_page" in names
    assert "get_interface" in names
    assert "get_interface_config" in names
    assert "list_page_versions" in names
    assert "list_interface_versions" in names


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
