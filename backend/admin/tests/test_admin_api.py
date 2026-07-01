import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

db_path = Path(tempfile.gettempdir()) / "admin-api-test.db"
if db_path.exists():
    db_path.unlink()

os.environ["ADMIN_API_DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["ADMIN_API_SECRET_KEY"] = "test-secret"
os.environ["ADMIN_API_DEFAULT_ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_API_DEFAULT_ADMIN_PASSWORD"] = "admin123"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.interfaces import validate_yaml_config  # noqa: E402


def auth_headers(client: TestClient) -> dict:
    response = client.post(
        "/api/admin/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer {}".format(response.json()["accessToken"])}


def create_project(client: TestClient, headers: dict) -> int:
    response = client.post(
        "/api/admin/projects",
        json={
            "code": "demo",
            "name": "Demo Project",
            "description": "demo",
            "baseUrl": "http://third-party.local",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["baseUrl"] == "http://third-party.local"
    return response.json()["id"]


def test_auth_login_refresh_logout_and_me() -> None:
    with TestClient(app) as client:
        failed = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert failed.status_code == 401

        login = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert login.status_code == 200
        tokens = login.json()
        headers = {"Authorization": "Bearer {}".format(tokens["accessToken"])}

        me = client.get("/api/admin/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["username"] == "admin"

        refreshed = client.post(
            "/api/admin/auth/refresh",
            json={"refreshToken": tokens["refreshToken"]},
        )
        assert refreshed.status_code == 200
        assert refreshed.json()["accessToken"] != tokens["accessToken"]

        logout = client.post(
            "/api/admin/auth/logout",
            json={"refreshToken": refreshed.json()["refreshToken"]},
            headers={"Authorization": "Bearer {}".format(refreshed.json()["accessToken"])},
        )
        assert logout.status_code == 200


def test_seeded_interface_configs_match_yaml_contract() -> None:
    with TestClient(app):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT p.code AS project_code, ai.code AS interface_code, c.yaml_text
            FROM interface_configs c
            JOIN app_interfaces ai ON ai.id = c.interface_id
            JOIN projects p ON p.id = ai.project_id
            ORDER BY p.code, ai.code
            """
        ).fetchall()
        conn.close()

    invalid = []
    for row in rows:
        try:
            validate_yaml_config(row["yaml_text"])
        except Exception as exc:  # pragma: no cover - assertion reports details
            invalid.append(f"{row['project_code']}/{row['interface_code']}: {exc}")
    assert invalid == []


def test_admin_crud_yaml_and_public_reads() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        project_id = create_project(client, headers)

        project_update = client.put(
            f"/api/admin/projects/{project_id}",
            json={"baseUrl": "http://third-party-updated.local"},
            headers=headers,
        )
        assert project_update.status_code == 200
        assert project_update.json()["baseUrl"] == "http://third-party-updated.local"

        unauthorized = client.get("/api/admin/projects")
        assert unauthorized.status_code == 401

        page = client.post(
            f"/api/admin/projects/{project_id}/pages",
            json={
                "code": "home",
                "name": "Home",
                "route": "/home",
                "sortOrder": 1,
                "config": {"title": "Home"},
            },
            headers=headers,
        )
        assert page.status_code == 201
        assert page.json()["route"] == "/home"
        page_id = page.json()["id"]

        page_update = client.put(
            f"/api/admin/pages/{page_id}",
            json={"name": "Home Updated", "config": {"title": "Home Updated"}},
            headers=headers,
        )
        assert page_update.status_code == 200

        page_versions = client.get(
            f"/api/admin/pages/{page_id}/versions",
            headers=headers,
        )
        assert page_versions.status_code == 200
        assert page_versions.json()["total"] == 2
        assert page_versions.json()["items"][0]["action"] == "update"

        page_v1 = client.get(
            f"/api/admin/pages/{page_id}/versions/1",
            headers=headers,
        )
        assert page_v1.status_code == 200
        assert page_v1.json()["snapshot"]["name"] == "Home"

        interface = client.post(
            f"/api/admin/projects/{project_id}/interfaces",
            json={
                "code": "query_user",
                "name": "Query User",
                "method": "GET",
                "path": "/users",
                "authMode": "bearer",
                "description": "query users",
            },
            headers=headers,
        )
        assert interface.status_code == 201
        interface_id = interface.json()["id"]

        invalid_yaml = client.post(
            "/api/admin/interfaces/config-yaml/validate",
            json={"yamlText": "version: 1\nrequest:\n  method: GET\n"},
            headers=headers,
        )
        assert invalid_yaml.status_code == 400

        valid_yaml = (
            "version: 1\n"
            "kind: api\n"
            "readOnly: true\n"
            "request:\n"
            "  method: GET\n"
            "  path: /users\n"
            "response:\n"
            "  dataPath: data\n"
        )
        validation = client.post(
            "/api/admin/interfaces/config-yaml/validate",
            json={"yamlText": valid_yaml},
            headers=headers,
        )
        assert validation.status_code == 200
        assert validation.json()["valid"] is True

        saved_config = client.put(
            f"/api/admin/interfaces/{interface_id}/config-yaml",
            json={"yamlText": valid_yaml},
            headers=headers,
        )
        assert saved_config.status_code == 200
        assert saved_config.json()["parsedConfig"]["request"]["path"] == "/users"

        interface_versions = client.get(
            f"/api/admin/interfaces/{interface_id}/versions",
            headers=headers,
        )
        assert interface_versions.status_code == 200
        assert interface_versions.json()["total"] == 2
        assert interface_versions.json()["items"][0]["action"] == "config"
        assert interface_versions.json()["items"][0]["snapshot"]["config"]["yamlText"] == valid_yaml

        public_pages = client.get("/api/app/projects/demo/pages")
        assert public_pages.status_code == 200
        assert public_pages.json()["total"] == 1
        assert public_pages.json()["page"] == 1
        assert public_pages.json()["pageSize"] == 20

        public_interfaces = client.get("/api/app/projects/demo/interfaces")
        assert public_interfaces.status_code == 200
        assert public_interfaces.json()["items"][0]["parsedConfig"]["request"]["method"] == "GET"

        public_project = client.get("/api/app/projects/demo")
        assert public_project.status_code == 200
        assert public_project.json()["baseUrl"] == "http://third-party-updated.local"

        deleted_page = client.delete(f"/api/admin/pages/{page_id}", headers=headers)
        assert deleted_page.status_code == 200
        page_versions_after_delete = client.get(
            f"/api/admin/pages/{page_id}/versions",
            headers=headers,
        )
        assert page_versions_after_delete.status_code == 200
        assert page_versions_after_delete.json()["items"][0]["action"] == "delete"

        deleted_interface = client.delete(
            f"/api/admin/interfaces/{interface_id}",
            headers=headers,
        )
        assert deleted_interface.status_code == 200
        interface_versions_after_delete = client.get(
            f"/api/admin/interfaces/{interface_id}/versions",
            headers=headers,
        )
        assert interface_versions_after_delete.status_code == 200
        assert interface_versions_after_delete.json()["items"][0]["action"] == "delete"


def test_yaml_rejects_executable_keys() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        response = client.post(
            "/api/admin/interfaces/config-yaml/validate",
            json={"yamlText": "version: 1\nrequest:\n  method: GET\n  path: /x\nscript: rm -rf /"},
            headers=headers,
        )
        assert response.status_code == 400


@pytest.mark.parametrize(
    ("field", "yaml_fragment"),
    [
        ("query", "  query: page\n"),
        ("body", "  body: payload\n"),
        ("headers", "  headers: Authorization\n"),
    ],
)
def test_yaml_rejects_non_mapping_request_sections(field: str, yaml_fragment: str) -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        yaml_text = (
            "version: 1\n"
            "kind: api\n"
            "readOnly: true\n"
            "request:\n"
            "  method: GET\n"
            "  path: /items\n"
            f"{yaml_fragment}"
            "response:\n"
            "  dataPath: data\n"
        )
        response = client.post(
            "/api/admin/interfaces/config-yaml/validate",
            json={"yamlText": yaml_text},
            headers=headers,
        )
        assert response.status_code == 400
        assert f"request.{field} must be a mapping" in response.json()["detail"]


@pytest.mark.parametrize(
    "interface_code_fragment",
    [
        "  interfaceCode: 123\n",
        "  interfaceCode: true\n",
        "  interfaceCode: ''\n",
        "  interfaceCode: '   '\n",
    ],
)
def test_yaml_rejects_invalid_auth_interface_code(interface_code_fragment: str) -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        yaml_text = (
            "version: 1\n"
            "kind: api\n"
            "readOnly: true\n"
            "request:\n"
            "  method: GET\n"
            "  path: /items\n"
            "response:\n"
            "  dataPath: data\n"
            "auth:\n"
            "  useProjectAuth: true\n"
            f"{interface_code_fragment}"
        )
        response = client.post(
            "/api/admin/interfaces/config-yaml/validate",
            json={"yamlText": yaml_text},
            headers=headers,
        )
        assert response.status_code == 400
        assert "auth.interfaceCode must be a non-empty string" in response.json()["detail"]


def test_bridge_yaml_contract_and_multiple_enabled_auth() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        project_id = client.post(
            "/api/admin/projects",
            json={
                "code": "bridge",
                "name": "Bridge",
                "description": "",
                "baseUrl": "http://bridge.local",
            },
            headers=headers,
        ).json()["id"]

        auth_interface = client.post(
            f"/api/admin/projects/{project_id}/interfaces",
            json={
                "code": "get_token",
                "name": "Get Token",
                "method": "POST",
                "path": "/api/agent-bridge/auth",
                "authMode": "none",
                "description": "bridge auth",
            },
            headers=headers,
        )
        assert auth_interface.status_code == 201

        auth_yaml = (
            "version: 1\n"
            "kind: auth\n"
            "request:\n"
            "  method: POST\n"
            "  path: /api/agent-bridge/auth\n"
            "response:\n"
            "  headerNamePath: headerName\n"
            "  headerValuePath: headerValue\n"
        )
        saved_auth = client.put(
            f"/api/admin/interfaces/{auth_interface.json()['id']}/config-yaml",
            json={"yamlText": auth_yaml},
            headers=headers,
        )
        assert saved_auth.status_code == 200
        assert saved_auth.json()["parsedConfig"]["kind"] == "auth"

        missing_auth_response = client.post(
            "/api/admin/interfaces/config-yaml/validate",
            json={
                "yamlText": (
                    "version: 1\n"
                    "kind: auth\n"
                    "request:\n"
                    "  method: POST\n"
                    "  path: /api/agent-bridge/auth\n"
                    "response:\n"
                    "  headerNamePath: headerName\n"
                )
            },
            headers=headers,
        )
        assert missing_auth_response.status_code == 400

        api_interface = client.post(
            f"/api/admin/projects/{project_id}/interfaces",
            json={
                "code": "user_list",
                "name": "User List",
                "method": "POST",
                "path": "/system/user/list",
                "authMode": "bearer",
                "description": "read-only users",
            },
            headers=headers,
        )
        assert api_interface.status_code == 201

        api_yaml = (
            "version: 1\n"
            "kind: api\n"
            "readOnly: true\n"
            "request:\n"
            "  method: POST\n"
            "  path: /system/user/list\n"
            "  contentType: application/x-www-form-urlencoded\n"
            "  body:\n"
            "    pageNum: '1'\n"
            "    pageSize: '10'\n"
            "response:\n"
            "  dataPath: rows\n"
            "auth:\n"
            "  useProjectAuth: true\n"
        )
        saved_api = client.put(
            f"/api/admin/interfaces/{api_interface.json()['id']}/config-yaml",
            json={"yamlText": api_yaml},
            headers=headers,
        )
        assert saved_api.status_code == 200
        assert saved_api.json()["parsedConfig"]["readOnly"] is True

        second_auth = client.post(
            f"/api/admin/projects/{project_id}/interfaces",
            json={
                "code": "get_token_again",
                "name": "Get Token Again",
                "method": "POST",
                "path": "/api/agent-bridge/auth2",
                "authMode": "none",
            },
            headers=headers,
        )
        assert second_auth.status_code == 201
        duplicate_auth_yaml = auth_yaml.replace(
            "path: /api/agent-bridge/auth",
            "path: /api/agent-bridge/auth2",
        )
        duplicate_auth = client.put(
            f"/api/admin/interfaces/{second_auth.json()['id']}/config-yaml",
            json={"yamlText": duplicate_auth_yaml},
            headers=headers,
        )
        assert duplicate_auth.status_code == 200
        assert duplicate_auth.json()["parsedConfig"]["kind"] == "auth"

        api_with_auth_code = (
            "version: 1\n"
            "kind: api\n"
            "readOnly: true\n"
            "request:\n"
            "  method: GET\n"
            "  path: /items\n"
            "  headers:\n"
            "    X-API-Key: '{secret.apiKey}'\n"
            "response:\n"
            "  dataPath: data\n"
            "auth:\n"
            "  useProjectAuth: true\n"
            "  interfaceCode: get_token_again\n"
        )
        validated = client.post(
            "/api/admin/interfaces/config-yaml/validate",
            json={"yamlText": api_with_auth_code},
            headers=headers,
        )
        assert validated.status_code == 200
        assert validated.json()["parsedConfig"]["auth"]["interfaceCode"] == "get_token_again"


def test_api_yaml_requires_read_only_flag() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        project_id = client.post(
            "/api/admin/projects",
            json={"code": "readonly", "name": "Readonly", "baseUrl": "http://x.local"},
            headers=headers,
        ).json()["id"]
        iface = client.post(
            f"/api/admin/projects/{project_id}/interfaces",
            json={
                "code": "unsafe",
                "name": "Unsafe",
                "method": "GET",
                "path": "/unsafe",
            },
            headers=headers,
        ).json()["id"]
        response = client.put(
            f"/api/admin/interfaces/{iface}/config-yaml",
            json={
                "yamlText": (
                    "version: 1\n"
                    "kind: api\n"
                    "request:\n"
                    "  method: GET\n"
                    "  path: /unsafe\n"
                    "response:\n"
                    "  dataPath: data\n"
                )
            },
            headers=headers,
        )
        assert response.status_code == 400

        write_iface = client.post(
            f"/api/admin/projects/{project_id}/interfaces",
            json={
                "code": "create_user",
                "name": "Create User",
                "method": "POST",
                "path": "/system/user",
            },
            headers=headers,
        ).json()["id"]
        write_yaml = client.put(
            f"/api/admin/interfaces/{write_iface}/config-yaml",
            json={
                "yamlText": (
                    "version: 1\n"
                    "kind: api\n"
                    "readOnly: false\n"
                    "request:\n"
                    "  method: POST\n"
                    "  path: /system/user\n"
                    "response:\n"
                    "  dataPath: data\n"
                )
            },
            headers=headers,
        )
        assert write_yaml.status_code == 200
        assert write_yaml.json()["parsedConfig"]["readOnly"] is False
