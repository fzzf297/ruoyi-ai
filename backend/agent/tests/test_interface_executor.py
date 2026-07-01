import os
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

os.environ.setdefault("AGENT_LLM_API_KEY", "test-key")
os.environ.setdefault("AGENT_ADMIN_BASE_URL", "http://localhost:8000")

from app.core.config import settings  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.schemas.admin_data import (  # noqa: E402
    InterfaceConfigOut,
    ProjectOut,
    PublicInterfaceOut,
)
from app.schemas.common import ListResponse  # noqa: E402
from app.services import auth_cache, interface_executor  # noqa: E402
from app.services.interface_executor import execute_interface  # noqa: E402


@pytest.fixture(autouse=True)
def _default_project_secrets() -> None:
    with patch(
        "app.services.interface_executor.get_project_secrets",
        return_value={"clientId": "agent", "clientSecret": "secret"},
    ):
        yield


@pytest.fixture(autouse=True)
def _clear_auth_cache() -> None:
    auth_cache.clear()
    yield
    auth_cache.clear()


def _project(base_url: str = "http://third-party.local") -> ProjectOut:
    return ProjectOut(
        id=1,
        code="demo",
        name="Demo",
        description="",
        baseUrl=base_url,
        status="enabled",
        createdAt="2026-01-01T00:00:00",
        updatedAt="2026-01-01T00:00:00",
    )


def _iface(
    code: str,
    method: str,
    path: str,
    parsed_config: Optional[dict],
) -> PublicInterfaceOut:
    return PublicInterfaceOut(
        id=2,
        projectId=1,
        code=code,
        name=code,
        method=method,
        path=path,
        authMode="none",
        status="enabled",
        description="",
        createdAt="2026-01-01T00:00:00",
        updatedAt="2026-01-01T00:00:00",
        parsedConfig=parsed_config,
    )


AUTH_HEADER_VALUE = {
    "version": 1,
    "kind": "auth",
    "request": {
        "method": "POST",
        "path": "/api/agent-bridge/auth",
        "contentType": "application/json",
        "body": {
            "clientId": "{secret.clientId}",
            "clientSecret": "{secret.clientSecret}",
        },
    },
    "response": {
        "headerNamePath": "headerName",
        "headerValuePath": "headerValue",
        "expiresInPath": "expiresIn",
    },
}

AUTH_TOKEN_PREFIX = {
    "version": 1,
    "kind": "auth",
    "request": {"method": "POST", "path": "/api/agent-bridge/auth"},
    "response": {
        "headerNamePath": "headerName",
        "tokenPath": "token",
        "tokenPrefix": "Bearer ",
    },
}

API_FORM_POST = {
    "version": 1,
    "kind": "api",
    "readOnly": True,
    "request": {
        "method": "POST",
        "path": "/system/user/list",
        "contentType": "application/x-www-form-urlencoded",
        "body": {"pageNum": "{pageNum}", "pageSize": "10"},
    },
    "response": {"dataPath": "rows"},
    "auth": {"useProjectAuth": True},
}


class FakeAdminClient:
    def __init__(
        self,
        project: Optional[ProjectOut] = None,
        target: Optional[PublicInterfaceOut] = None,
        interfaces: Optional[list[PublicInterfaceOut]] = None,
        config: Optional[InterfaceConfigOut] = None,
    ) -> None:
        self.project = project or _project()
        self.target = target or _iface("user_list", "POST", "/system/user/list", API_FORM_POST)
        self.interfaces = (
            [_iface("get_token", "POST", "/api/agent-bridge/auth", AUTH_HEADER_VALUE)]
            if interfaces is None
            else interfaces
        )
        self.config = config

    async def get_project(self, project_code: str) -> ProjectOut:
        return self.project

    async def get_interface(self, project_code: str, interface_code: str) -> PublicInterfaceOut:
        return self.target

    async def get_interface_config(
        self, project_code: str, interface_code: str
    ) -> InterfaceConfigOut:
        return self.config or InterfaceConfigOut(
            interfaceId=self.target.id,
            yamlText="version: 1\n",
            parsedConfig=self.target.parsedConfig or {},
            createdAt="2026-01-01T00:00:00",
            updatedAt="2026-01-01T00:00:00",
        )

    async def list_interfaces(
        self, project_code: str, page: int = 1, page_size: int = 20
    ) -> ListResponse[PublicInterfaceOut]:
        return ListResponse(
            items=self.interfaces,
            total=len(self.interfaces),
            page=page,
            pageSize=page_size,
        )


def _patch_http(responses: list[httpx.Response]):
    queue = list(responses)
    stream_calls: list[tuple] = []
    client = MagicMock()

    def mock_stream(method, url, **kwargs):
        stream_calls.append((method, url, kwargs))
        if not queue:
            raise RuntimeError("no mock responses left")
        response = queue.pop(0)

        @asynccontextmanager
        async def _inner():
            yield response

        return _inner()

    client.stream = MagicMock(side_effect=mock_stream)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.stream_calls = stream_calls
    return patch(
        "app.services.interface_executor.httpx.AsyncClient",
        return_value=client,
    ), client


@pytest.mark.anyio
async def test_execute_interface_fetches_header_value_auth_and_form_post() -> None:
    auth_response = httpx.Response(
        200,
        json={
            "headerName": "Authorization",
            "headerValue": "Bearer abc",
            "expiresIn": 3600,
        },
    )
    api_response = httpx.Response(200, json={"rows": [{"userName": "admin"}], "total": 1})
    http_patch, http_client = _patch_http([auth_response, api_response])
    secrets = {"clientId": "agent", "clientSecret": "secret"}
    with (
        patch.object(interface_executor, "admin_client", new=FakeAdminClient()),
        patch(
            "app.services.interface_executor.get_project_secrets",
            return_value=secrets,
        ),
        http_patch,
    ):
        result = await execute_interface("demo", "user_list", {"pageNum": "2"})

    assert result["data"] == [{"userName": "admin"}]
    auth_call = http_client.stream_calls[0]
    auth_kwargs = auth_call[2]
    assert auth_kwargs["json"] == {"clientId": "agent", "clientSecret": "secret"}
    api_kwargs = http_client.stream_calls[1][2]
    assert api_kwargs["headers"]["Authorization"] == "Bearer abc"
    assert api_kwargs["data"] == {"pageNum": "2", "pageSize": "10"}


@pytest.mark.anyio
async def test_execute_interface_rejects_write_interface() -> None:
    write_config = {
        "version": 1,
        "kind": "api",
        "readOnly": False,
        "request": {
            "method": "POST",
            "path": "/system/user",
            "contentType": "application/json",
            "body": {"userName": "{userName}", "loginName": "{loginName}"},
        },
        "response": {"dataPath": "data"},
        "auth": {"useProjectAuth": True},
    }
    fake_admin = FakeAdminClient(
        target=_iface("create_user", "POST", "/system/user", write_config),
    )
    with patch.object(interface_executor, "admin_client", new=fake_admin):
        with pytest.raises(AppError) as exc_info:
            await execute_interface(
                "demo",
                "create_user",
                {"userName": "张三", "loginName": "zhangsan"},
            )
        assert exc_info.value.message == "INTERFACE_WRITE_NOT_ALLOWED"
        assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    ("parsed_config", "error_message"),
    [
        (
            {
                "version": 1,
                "kind": "api",
                "readOnly": True,
                "request": {"method": "GET", "path": "/x", "headers": "bad"},
                "response": {"dataPath": "."},
            },
            "INTERFACE_MAPPING_INVALID",
        ),
        (
            {
                "version": 1,
                "kind": "api",
                "readOnly": True,
                "request": {"method": "GET", "path": "/x"},
                "response": {"dataPath": "."},
                "auth": {"useProjectAuth": True, "interfaceCode": 123},
            },
            "AUTH_INTERFACE_CODE_INVALID",
        ),
        (
            {
                "version": 1,
                "kind": "api",
                "readOnly": True,
                "request": {"method": "GET", "path": "/x"},
                "response": {"dataPath": "."},
                "auth": {"useProjectAuth": True, "interfaceCode": ""},
            },
            "AUTH_INTERFACE_CODE_INVALID",
        ),
    ],
)
@pytest.mark.anyio
async def test_execute_interface_rejects_invalid_config_sections(
    parsed_config: dict, error_message: str
) -> None:
    fake_admin = FakeAdminClient(
        target=_iface("bad_api", "GET", "/x", parsed_config),
        interfaces=[],
    )
    with patch.object(interface_executor, "admin_client", new=fake_admin):
        with pytest.raises(AppError) as exc_info:
            await execute_interface("demo", "bad_api", {})
        assert exc_info.value.message == error_message
        assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_execute_interface_supports_token_prefix_auth_and_get_query() -> None:
    api_config = {
        "version": 1,
        "kind": "api",
        "readOnly": True,
        "request": {
            "method": "GET",
            "path": "/users/{userId}",
            "query": {"keyword": "{keyword}"},
        },
        "response": {"dataPath": "."},
        "auth": {"useProjectAuth": True},
    }
    fake_admin = FakeAdminClient(
        target=_iface("user_detail", "GET", "/users/{userId}", api_config),
        interfaces=[_iface("get_token", "POST", "/api/agent-bridge/auth", AUTH_TOKEN_PREFIX)],
    )
    auth_response = httpx.Response(200, json={"headerName": "Authorization", "token": "abc"})
    api_response = httpx.Response(200, json={"id": 7, "userName": "zhangsan"})
    http_patch, http_client = _patch_http([auth_response, api_response])
    with patch.object(interface_executor, "admin_client", new=fake_admin), http_patch:
        result = await execute_interface(
            "demo", "user_detail", {"userId": 7, "keyword": "zhang"}
        )

    assert result["data"] == {"id": 7, "userName": "zhangsan"}
    api_args = http_client.stream_calls[1]
    assert api_args[1] == "http://third-party.local/users/7"
    assert api_args[2]["params"] == {"keyword": "zhang"}
    assert api_args[2]["headers"]["Authorization"] == "Bearer abc"


@pytest.mark.anyio
async def test_execute_interface_url_encodes_path_params() -> None:
    api_config = {
        "version": 1,
        "kind": "api",
        "readOnly": True,
        "request": {"method": "GET", "path": "/users/{userId}"},
        "response": {"dataPath": "."},
    }
    fake_admin = FakeAdminClient(
        target=_iface("user_lookup", "GET", "/users/{userId}", api_config),
        interfaces=[],
    )
    api_response = httpx.Response(200, json={"ok": True})
    http_patch, http_client = _patch_http([api_response])
    with patch.object(interface_executor, "admin_client", new=fake_admin), http_patch:
        await execute_interface("demo", "user_lookup", {"userId": "../x?y=1"})

    api_args = http_client.stream_calls[0]
    assert api_args[1] == "http://third-party.local/users/..%2Fx%3Fy%3D1"


@pytest.mark.anyio
async def test_execute_interface_rejects_secret_in_path() -> None:
    api_config = {
        "version": 1,
        "kind": "api",
        "readOnly": True,
        "request": {"method": "GET", "path": "/users/{secret.clientId}"},
        "response": {"dataPath": "."},
    }
    fake_admin = FakeAdminClient(
        target=_iface("bad_path", "GET", "/users/{secret.clientId}", api_config),
        interfaces=[],
    )
    with patch.object(interface_executor, "admin_client", new=fake_admin):
        with pytest.raises(AppError) as exc_info:
            await execute_interface("demo", "bad_path", {})
        assert exc_info.value.message == "INTERFACE_PATH_SECRET_NOT_ALLOWED"


@pytest.mark.anyio
async def test_execute_interface_falls_back_to_config_endpoint() -> None:
    target = _iface("user_list", "POST", "/system/user/list", None)
    fake_admin = FakeAdminClient(
        target=target,
        config=InterfaceConfigOut(
            interfaceId=target.id,
            yamlText="version: 1\n",
            parsedConfig=API_FORM_POST,
            createdAt="2026-01-01T00:00:00",
            updatedAt="2026-01-01T00:00:00",
        ),
    )
    http_patch, _ = _patch_http(
        [
            httpx.Response(200, json={"headerName": "Authorization", "headerValue": "Bearer abc"}),
            httpx.Response(200, json={"rows": []}),
        ]
    )
    with patch.object(interface_executor, "admin_client", new=fake_admin), http_patch:
        result = await execute_interface("demo", "user_list", {"pageNum": "1"})

    assert result["data"] == []


@pytest.mark.anyio
async def test_execute_interface_rejects_unsafe_or_misconfigured_interfaces() -> None:
    cases = [
        (
            FakeAdminClient(project=_project(base_url="ftp://bad.local")),
            "PROJECT_BASE_URL_INVALID",
        ),
        (
            FakeAdminClient(project=_project(base_url="")),
            "PROJECT_BASE_URL_REQUIRED",
        ),
        (
            FakeAdminClient(project=_project(base_url="http://127.0.0.1")),
            "THIRD_PARTY_HOST_NOT_ALLOWED",
        ),
        (
            FakeAdminClient(
                target=_iface(
                    "unsafe",
                    "POST",
                    "/unsafe",
                    {"version": 1, "kind": "api", "request": {"method": "POST", "path": "/unsafe"}},
                )
            ),
            "INTERFACE_READ_ONLY_REQUIRED",
        ),
        (
            FakeAdminClient(
                target=_iface(
                    "trace_user",
                    "TRACE",
                    "/users",
                    {
                        "version": 1,
                        "kind": "api",
                        "readOnly": True,
                        "request": {"method": "TRACE", "path": "/users"},
                    },
                )
            ),
            "INTERFACE_METHOD_NOT_ALLOWED",
        ),
        (
            FakeAdminClient(
                target=_iface(
                    "patch_user",
                    "PATCH",
                    "/users/1",
                    {
                        "version": 1,
                        "kind": "api",
                        "readOnly": True,
                        "request": {"method": "PATCH", "path": "/users/1"},
                    },
                )
            ),
            "INTERFACE_METHOD_NOT_ALLOWED",
        ),
        (
            FakeAdminClient(
                target=_iface(
                    "delete_user",
                    "DELETE",
                    "/users/1",
                    {
                        "version": 1,
                        "kind": "api",
                        "readOnly": True,
                        "request": {"method": "DELETE", "path": "/users/1"},
                    },
                )
            ),
            "INTERFACE_METHOD_NOT_ALLOWED",
        ),
        (
            FakeAdminClient(interfaces=[]),
            "PROJECT_AUTH_NOT_FOUND",
        ),
        (
            FakeAdminClient(
                interfaces=[
                    _iface("auth1", "POST", "/auth1", AUTH_HEADER_VALUE),
                    _iface("auth2", "POST", "/auth2", AUTH_TOKEN_PREFIX),
                ]
            ),
            "PROJECT_AUTH_NOT_UNIQUE",
        ),
    ]
    for fake_admin, message in cases:
        with patch.object(interface_executor, "admin_client", new=fake_admin):
            with pytest.raises(AppError) as exc_info:
                await execute_interface("demo", "user_list", {"pageNum": "1"})
            assert message in exc_info.value.message


@pytest.mark.anyio
async def test_execute_interface_rejects_disallowed_host_with_allowlist() -> None:
    fake_admin = FakeAdminClient(project=_project(base_url="http://third-party.local"))
    patched = replace(settings, third_party_allowed_hosts=["allowed.example"])
    with (
        patch.object(interface_executor, "settings", patched),
        patch.object(interface_executor, "admin_client", new=fake_admin),
    ):
        with pytest.raises(AppError) as exc_info:
            await execute_interface("demo", "user_list", {"pageNum": "1"})
        assert exc_info.value.message == "THIRD_PARTY_HOST_NOT_ALLOWED"


@pytest.mark.anyio
async def test_execute_interface_converts_third_party_errors() -> None:
    fake_admin = FakeAdminClient()
    client = MagicMock()

    @asynccontextmanager
    async def stream_timeout(method, url, **kwargs):
        raise httpx.TimeoutException("slow")
        yield  # pragma: no cover

    client.stream = stream_timeout
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    with (
        patch.object(interface_executor, "admin_client", new=fake_admin),
        patch("app.services.interface_executor.httpx.AsyncClient", return_value=client),
    ):
        with pytest.raises(AppError) as exc_info:
            await execute_interface("demo", "user_list", {"pageNum": "1"})
        assert exc_info.value.status_code == 504

    http_patch, _ = _patch_http([httpx.Response(200, content=b"not-json")])
    with patch.object(interface_executor, "admin_client", new=fake_admin), http_patch:
        with pytest.raises(AppError) as exc_info:
            await execute_interface("demo", "user_list", {"pageNum": "1"})
        assert exc_info.value.status_code == 502


@pytest.mark.anyio
async def test_execute_interface_rejects_oversized_response() -> None:
    fake_admin = FakeAdminClient(interfaces=[])
    api_config = {
        "version": 1,
        "kind": "api",
        "readOnly": True,
        "request": {"method": "GET", "path": "/big"},
        "response": {"dataPath": "."},
    }
    fake_admin.target = _iface("big", "GET", "/big", api_config)
    oversized = httpx.Response(200, content=b"x" * 32)

    @asynccontextmanager
    async def stream(method, url, **kwargs):
        response = oversized
        original_iter = response.aiter_bytes

        async def chunked():
            async for chunk in original_iter():
                yield chunk

        response.aiter_bytes = chunked
        yield response

    client = MagicMock()
    client.stream = stream
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    patched = replace(settings, third_party_max_response_bytes=16)
    with (
        patch.object(interface_executor, "settings", patched),
        patch.object(interface_executor, "admin_client", new=fake_admin),
        patch("app.services.interface_executor.httpx.AsyncClient", return_value=client),
    ):
        with pytest.raises(AppError) as exc_info:
            await execute_interface("demo", "big", {})
        assert exc_info.value.message == "THIRD_PARTY_RESPONSE_TOO_LARGE"


@pytest.mark.anyio
async def test_execute_interface_caches_auth_headers() -> None:
    auth_response = httpx.Response(
        200,
        json={"headerName": "Authorization", "headerValue": "Bearer abc", "expiresIn": 3600},
    )
    api_response = httpx.Response(200, json={"rows": []})
    http_patch, http_client = _patch_http(
        [auth_response, api_response, api_response]
    )
    with patch.object(interface_executor, "admin_client", new=FakeAdminClient()), http_patch:
        await execute_interface("demo", "user_list", {"pageNum": "1"})
        await execute_interface("demo", "user_list", {"pageNum": "2"})

    assert len(http_client.stream_calls) == 3


@pytest.mark.anyio
async def test_execute_interface_invalidates_cache_when_auth_config_changes() -> None:
    auth_v1 = dict(AUTH_HEADER_VALUE)
    auth_v2 = dict(AUTH_HEADER_VALUE)
    auth_v2["request"] = dict(AUTH_HEADER_VALUE["request"])
    auth_v2["request"]["path"] = "/api/agent-bridge/auth-v2"

    class SwitchingAdmin(FakeAdminClient):
        def __init__(self) -> None:
            super().__init__()
            self.version = 1

        async def list_interfaces(
            self, project_code: str, page: int = 1, page_size: int = 20
        ) -> ListResponse[PublicInterfaceOut]:
            auth_cfg = auth_v1 if self.version == 1 else auth_v2
            return ListResponse(
                items=[_iface("get_token", "POST", "/auth", auth_cfg)],
                total=1,
                page=page,
                pageSize=page_size,
            )

    auth_response = httpx.Response(
        200,
        json={"headerName": "Authorization", "headerValue": "Bearer abc", "expiresIn": 3600},
    )
    api_response = httpx.Response(200, json={"rows": []})
    http_patch, http_client = _patch_http(
        [auth_response, api_response, auth_response, api_response]
    )
    admin = SwitchingAdmin()
    with patch.object(interface_executor, "admin_client", new=admin), http_patch:
        await execute_interface("demo", "user_list", {"pageNum": "1"})
        admin.version = 2
        await execute_interface("demo", "user_list", {"pageNum": "2"})

    assert len(http_client.stream_calls) == 4


@pytest.mark.anyio
async def test_execute_interface_retries_after_401() -> None:
    auth_response = httpx.Response(
        200,
        json={"headerName": "Authorization", "headerValue": "Bearer abc", "expiresIn": 60},
    )
    unauthorized = httpx.Response(401, json={"msg": "expired"})
    ok_response = httpx.Response(200, json={"rows": [{"userName": "u1"}]})
    http_patch, http_client = _patch_http(
        [auth_response, unauthorized, auth_response, ok_response]
    )
    with patch.object(interface_executor, "admin_client", new=FakeAdminClient()), http_patch:
        result = await execute_interface("demo", "user_list", {"pageNum": "1"})

    assert result["data"] == [{"userName": "u1"}]
    assert len(http_client.stream_calls) == 4


@pytest.mark.anyio
async def test_execute_interface_renders_request_headers_with_secret() -> None:
    api_config = {
        "version": 1,
        "kind": "api",
        "readOnly": True,
        "request": {
            "method": "GET",
            "path": "/data",
            "headers": {"X-API-Key": "{secret.apiKey}"},
        },
        "response": {"dataPath": "."},
    }
    fake_admin = FakeAdminClient(
        target=_iface("data_api", "GET", "/data", api_config),
        interfaces=[],
    )
    api_response = httpx.Response(200, json={"ok": True})
    http_patch, http_client = _patch_http([api_response])
    with (
        patch.object(interface_executor, "admin_client", new=fake_admin),
        patch(
            "app.services.interface_executor.get_project_secrets",
            return_value={"apiKey": "sk-test"},
        ),
        http_patch,
    ):
        await execute_interface("demo", "data_api", {})

    api_kwargs = http_client.stream_calls[0][2]
    assert api_kwargs["headers"]["X-API-Key"] == "sk-test"


@pytest.mark.anyio
async def test_execute_interface_uses_auth_interface_code() -> None:
    auth_a = {
        "version": 1,
        "kind": "auth",
        "request": {"method": "POST", "path": "/auth/a"},
        "response": {
            "headerNamePath": "headerName",
            "headerValuePath": "headerValue",
        },
    }
    auth_b = {
        "version": 1,
        "kind": "auth",
        "request": {"method": "POST", "path": "/auth/b"},
        "response": {
            "headerNamePath": "headerName",
            "headerValuePath": "headerValue",
        },
    }
    api_config = {
        "version": 1,
        "kind": "api",
        "readOnly": True,
        "request": {"method": "GET", "path": "/items"},
        "response": {"dataPath": "items"},
        "auth": {"useProjectAuth": True, "interfaceCode": "auth_b"},
    }
    fake_admin = FakeAdminClient(
        target=_iface("item_list", "GET", "/items", api_config),
        interfaces=[
            _iface("auth_a", "POST", "/auth/a", auth_a),
            _iface("auth_b", "POST", "/auth/b", auth_b),
        ],
    )
    auth_response = httpx.Response(
        200,
        json={"headerName": "Authorization", "headerValue": "Bearer from-b"},
    )
    api_response = httpx.Response(200, json={"items": []})
    http_patch, http_client = _patch_http([auth_response, api_response])
    with patch.object(interface_executor, "admin_client", new=fake_admin), http_patch:
        result = await execute_interface("demo", "item_list", {})

    assert result["data"] == []
    auth_url = http_client.stream_calls[0][1]
    assert auth_url == "http://third-party.local/auth/b"
    api_kwargs = http_client.stream_calls[1][2]
    assert api_kwargs["headers"]["Authorization"] == "Bearer from-b"


@pytest.mark.anyio
async def test_execute_interface_rejects_missing_auth_interface_code() -> None:
    api_config = {
        "version": 1,
        "kind": "api",
        "readOnly": True,
        "request": {"method": "GET", "path": "/items"},
        "response": {"dataPath": "items"},
        "auth": {"useProjectAuth": True, "interfaceCode": "missing_auth"},
    }
    fake_admin = FakeAdminClient(
        target=_iface("item_list", "GET", "/items", api_config),
        interfaces=[_iface("auth_a", "POST", "/auth/a", AUTH_HEADER_VALUE)],
    )
    with patch.object(interface_executor, "admin_client", new=fake_admin):
        with pytest.raises(AppError) as exc_info:
            await execute_interface("demo", "item_list", {})
        assert exc_info.value.message == "PROJECT_AUTH_NOT_FOUND"
        assert exc_info.value.status_code == 400
        assert exc_info.value.status_code == 400
