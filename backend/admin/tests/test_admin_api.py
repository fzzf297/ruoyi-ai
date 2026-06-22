import os
import tempfile
from pathlib import Path

db_path = Path(tempfile.gettempdir()) / "admin-api-test.db"
if db_path.exists():
    db_path.unlink()

os.environ["ADMIN_API_DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["ADMIN_API_SECRET_KEY"] = "test-secret"
os.environ["ADMIN_API_DEFAULT_ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_API_DEFAULT_ADMIN_PASSWORD"] = "admin123"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


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
        json={"code": "demo", "name": "Demo Project", "description": "demo"},
        headers=headers,
    )
    assert response.status_code == 201
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


def test_admin_crud_yaml_and_public_reads() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        project_id = create_project(client, headers)

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
            "version: 1\nrequest:\n  method: GET\n  path: /users\nresponse:\n  dataPath: data\n"
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

        public_interfaces = client.get("/api/app/projects/demo/interfaces")
        assert public_interfaces.status_code == 200
        assert public_interfaces.json()["items"][0]["parsedConfig"]["request"]["method"] == "GET"

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
