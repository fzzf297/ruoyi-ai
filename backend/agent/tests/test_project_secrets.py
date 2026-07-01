import json

from app.core.project_secrets import get_project_secrets, load_all_project_secrets


def test_load_project_secrets_from_json(monkeypatch) -> None:
    monkeypatch.setenv(
        "AGENT_PROJECT_SECRETS",
        json.dumps(
            {
                "ruoyi-classic": {
                    "clientId": "agent",
                    "clientSecret": "secret",
                }
            }
        ),
    )
    loaded = load_all_project_secrets()
    assert get_project_secrets("ruoyi-classic", loaded)["clientId"] == "agent"


def test_load_project_secrets_from_env_prefix(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_PROJECT_SECRETS", raising=False)
    monkeypatch.setenv("AGENT_PROJECT_DEMO_SAAS__CLIENT_ID", "id-1")
    monkeypatch.setenv("AGENT_PROJECT_DEMO_SAAS__CLIENT_SECRET", "sec-1")
    loaded = load_all_project_secrets()
    secrets = get_project_secrets("demo-saas", loaded)
    assert secrets["clientId"] == "id-1"
    assert secrets["clientSecret"] == "sec-1"
