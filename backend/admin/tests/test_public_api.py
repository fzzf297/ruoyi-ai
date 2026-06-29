import os
import tempfile
from pathlib import Path

db_path = Path(tempfile.gettempdir()) / "admin-api-public-test.db"
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


def create_project(client: TestClient, headers: dict, code: str, status: str = "enabled") -> int:
    response = client.post(
        "/api/admin/projects",
        json={"code": code, "name": code.title(), "description": "", "status": status},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_page(
    client: TestClient,
    headers: dict,
    project_id: int,
    code: str,
    status: str = "enabled",
) -> int:
    response = client.post(
        f"/api/admin/projects/{project_id}/pages",
        json={
            "code": code,
            "name": code.title(),
            "route": f"/{code}",
            "sortOrder": 0,
            "config": {},
            "status": status,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_interface(
    client: TestClient,
    headers: dict,
    project_id: int,
    code: str,
    status: str = "enabled",
) -> int:
    response = client.post(
        f"/api/admin/projects/{project_id}/interfaces",
        json={
            "code": code,
            "name": code.title(),
            "method": "GET",
            "path": f"/{code}",
            "authMode": "none",
            "status": status,
            "description": "",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def save_interface_config(
    client: TestClient, headers: dict, interface_id: int, path: str = "/items"
) -> None:
    yaml_text = (
        f"version: 1\nrequest:\n  method: GET\n  path: {path}\nresponse:\n  dataPath: data\n"
    )
    response = client.put(
        f"/api/admin/interfaces/{interface_id}/config-yaml",
        json={"yamlText": yaml_text},
        headers=headers,
    )
    assert response.status_code == 200


def test_list_public_projects_enabled_filter_pagination_and_empty() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)

        create_project(client, headers, "alpha")
        create_project(client, headers, "beta")
        create_project(client, headers, "gamma", status="disabled")

        res = client.get("/api/app/projects")
        assert res.status_code == 200
        body = res.json()
        assert body["total"] >= 2
        assert body["page"] == 1
        assert body["pageSize"] == 20
        codes = {item["code"] for item in body["items"]}
        assert "alpha" in codes
        assert "beta" in codes
        assert "gamma" not in codes

        page1 = client.get("/api/app/projects?page=1&pageSize=1")
        assert page1.status_code == 200
        assert page1.json()["total"] >= 2
        assert len(page1.json()["items"]) == 1

        page2 = client.get("/api/app/projects?page=2&pageSize=1")
        assert page2.status_code == 200
        assert len(page2.json()["items"]) == 1
        assert {item["code"] for item in page2.json()["items"]} != {
            item["code"] for item in page1.json()["items"]
        }

        beyond = client.get("/api/app/projects?page=999&pageSize=20")
        assert beyond.status_code == 200
        assert beyond.json()["items"] == []


def test_get_public_project() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)

        not_found = client.get("/api/app/projects/nope")
        assert not_found.status_code == 404

        create_project(client, headers, "delta")
        create_project(client, headers, "epsilon", status="disabled")

        ok = client.get("/api/app/projects/delta")
        assert ok.status_code == 200
        assert ok.json()["code"] == "delta"
        assert ok.json()["status"] == "enabled"

        disabled = client.get("/api/app/projects/epsilon")
        assert disabled.status_code == 404

        missing = client.get("/api/app/projects/missing")
        assert missing.status_code == 404


def test_get_public_page() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)

        project_missing = client.get("/api/app/projects/nope/pages/home")
        assert project_missing.status_code == 404

        project_id = create_project(client, headers, "zeta")
        create_page(client, headers, project_id, "home")
        create_page(client, headers, project_id, "settings", status="disabled")

        ok = client.get("/api/app/projects/zeta/pages/home")
        assert ok.status_code == 200
        assert ok.json()["code"] == "home"
        assert ok.json()["status"] == "enabled"
        assert ok.json()["route"] == "/home"

        disabled = client.get("/api/app/projects/zeta/pages/settings")
        assert disabled.status_code == 404

        not_found = client.get("/api/app/projects/zeta/pages/missing")
        assert not_found.status_code == 404

        project_not_found = client.get("/api/app/projects/missing/pages/home")
        assert project_not_found.status_code == 404


def test_get_public_interface_and_config() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)

        project_missing = client.get("/api/app/projects/nope/interfaces/api")
        assert project_missing.status_code == 404

        project_id = create_project(client, headers, "eta")
        iface_with_cfg = create_interface(client, headers, project_id, "api")
        create_interface(client, headers, project_id, "plain")
        create_interface(client, headers, project_id, "off", status="disabled")
        save_interface_config(client, headers, iface_with_cfg, path="/api")

        ok = client.get("/api/app/projects/eta/interfaces/api")
        assert ok.status_code == 200
        body = ok.json()
        assert body["code"] == "api"
        assert body["status"] == "enabled"
        assert body["parsedConfig"]["request"]["method"] == "GET"

        no_cfg = client.get("/api/app/projects/eta/interfaces/plain")
        assert no_cfg.status_code == 200
        assert no_cfg.json()["parsedConfig"] is None

        disabled = client.get("/api/app/projects/eta/interfaces/off")
        assert disabled.status_code == 404

        missing = client.get("/api/app/projects/eta/interfaces/missing")
        assert missing.status_code == 404

        cfg = client.get("/api/app/projects/eta/interfaces/api/config")
        assert cfg.status_code == 200
        cfg_body = cfg.json()
        assert cfg_body["interfaceId"] == iface_with_cfg
        assert cfg_body["yamlText"]
        assert cfg_body["parsedConfig"]["request"]["path"] == "/api"

        empty_cfg = client.get("/api/app/projects/eta/interfaces/plain/config")
        assert empty_cfg.status_code == 200
        assert empty_cfg.json()["yamlText"] == ""
        assert empty_cfg.json()["parsedConfig"] == {}

        cfg_disabled = client.get("/api/app/projects/eta/interfaces/off/config")
        assert cfg_disabled.status_code == 404

        cfg_project_missing = client.get("/api/app/projects/missing/interfaces/api/config")
        assert cfg_project_missing.status_code == 404


def test_list_public_pages_and_interfaces_pagination() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        project_id = create_project(client, headers, "theta")

        for i in range(3):
            create_page(client, headers, project_id, f"page{i}")
        for i in range(3):
            create_interface(client, headers, project_id, f"iface{i}")

        empty_pages = client.get("/api/app/projects/missing/pages")
        assert empty_pages.status_code == 404

        pages = client.get("/api/app/projects/theta/pages")
        assert pages.status_code == 200
        assert pages.json()["total"] == 3
        assert pages.json()["page"] == 1
        assert pages.json()["pageSize"] == 20
        assert len(pages.json()["items"]) == 3

        pages_p1 = client.get("/api/app/projects/theta/pages?page=1&pageSize=2")
        assert pages_p1.json()["total"] == 3
        assert len(pages_p1.json()["items"]) == 2

        pages_p2 = client.get("/api/app/projects/theta/pages?page=2&pageSize=2")
        assert len(pages_p2.json()["items"]) == 1

        empty_ifaces = client.get("/api/app/projects/missing/interfaces")
        assert empty_ifaces.status_code == 404

        ifaces = client.get("/api/app/projects/theta/interfaces")
        assert ifaces.status_code == 200
        assert ifaces.json()["total"] == 3
        assert len(ifaces.json()["items"]) == 3

        ifaces_p1 = client.get("/api/app/projects/theta/interfaces?page=1&pageSize=2")
        assert ifaces_p1.json()["total"] == 3
        assert len(ifaces_p1.json()["items"]) == 2


def test_list_public_page_versions_empty_and_present() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        project_id = create_project(client, headers, "iota")
        page_id = create_page(client, headers, project_id, "vpage")

        only_create = client.get("/api/app/projects/iota/pages/vpage/versions")
        assert only_create.status_code == 200
        assert only_create.json()["total"] == 1
        assert only_create.json()["items"][0]["action"] == "create"

        client.put(
            f"/api/admin/pages/{page_id}",
            json={"name": "VPage Updated"},
            headers=headers,
        )

        present = client.get("/api/app/projects/iota/pages/vpage/versions")
        assert present.status_code == 200
        assert present.json()["total"] == 2
        assert present.json()["items"][0]["action"] == "update"
        assert present.json()["items"][0]["entityId"] == page_id

        paged = client.get(
            "/api/app/projects/iota/pages/vpage/versions?page=1&pageSize=1"
        )
        assert paged.json()["total"] == 2
        assert len(paged.json()["items"]) == 1

        project_missing = client.get("/api/app/projects/missing/pages/vpage/versions")
        assert project_missing.status_code == 404

        page_missing = client.get("/api/app/projects/iota/pages/nope/versions")
        assert page_missing.status_code == 404


def test_list_public_interface_versions_empty_and_present() -> None:
    with TestClient(app) as client:
        headers = auth_headers(client)
        project_id = create_project(client, headers, "kappa")
        iface_id = create_interface(client, headers, project_id, "viface")

        only_create = client.get("/api/app/projects/kappa/interfaces/viface/versions")
        assert only_create.status_code == 200
        assert only_create.json()["total"] == 1
        assert only_create.json()["items"][0]["action"] == "create"

        save_interface_config(client, headers, iface_id, path="/viface")

        present = client.get("/api/app/projects/kappa/interfaces/viface/versions")
        assert present.status_code == 200
        assert present.json()["total"] == 2
        assert present.json()["items"][0]["action"] == "config"

        paged = client.get(
            "/api/app/projects/kappa/interfaces/viface/versions?page=1&pageSize=1"
        )
        assert paged.json()["total"] == 2
        assert len(paged.json()["items"]) == 1

        project_missing = client.get(
            "/api/app/projects/missing/interfaces/viface/versions"
        )
        assert project_missing.status_code == 404

        iface_missing = client.get("/api/app/projects/kappa/interfaces/nope/versions")
        assert iface_missing.status_code == 404
