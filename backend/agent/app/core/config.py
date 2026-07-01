import os
from dataclasses import dataclass
from pathlib import Path

from app.core.project_secrets import load_all_project_secrets

BASE_DIR = Path(__file__).resolve().parents[2]


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_database_url(value: str) -> str:
    prefix = "sqlite:///"
    if not value.startswith(prefix):
        return value
    raw_path = value[len(prefix) :]
    path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return prefix + str(path)


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    database_url: str
    cors_origins: list[str]
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    admin_base_url: str
    admin_timeout: int
    rate_limit_per_minute: int
    max_session_messages: int
    project_secrets: dict[str, dict[str, str]]
    third_party_max_response_bytes: int
    third_party_allowed_hosts: list[str]


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("AGENT_API_APP_NAME", "Agent API"),
        environment=os.getenv("AGENT_API_ENV", "local"),
        database_url=_resolve_database_url(
            os.getenv("AGENT_API_DATABASE_URL", "sqlite:///data/agent.db")
        ),
        cors_origins=_csv(os.getenv("AGENT_API_CORS_ORIGINS", "*")) or ["*"],
        llm_base_url=os.getenv("AGENT_LLM_BASE_URL", "https://api.deepseek.com"),
        llm_api_key=os.getenv("AGENT_LLM_API_KEY", "change-me"),
        llm_model=os.getenv("AGENT_LLM_MODEL", "deepseek-chat"),
        admin_base_url=os.getenv("AGENT_ADMIN_BASE_URL", "http://localhost:8000"),
        admin_timeout=int(os.getenv("AGENT_ADMIN_TIMEOUT", "10")),
        rate_limit_per_minute=int(os.getenv("AGENT_RATE_LIMIT_PER_MINUTE", "30")),
        max_session_messages=int(os.getenv("AGENT_MAX_SESSION_MESSAGES", "100")),
        project_secrets=load_all_project_secrets(),
        third_party_max_response_bytes=int(
            os.getenv("AGENT_THIRD_PARTY_MAX_RESPONSE_BYTES", "1048576")
        ),
        third_party_allowed_hosts=_csv(
            os.getenv("AGENT_THIRD_PARTY_ALLOWED_HOSTS", "")
        ),
    )


settings = load_settings()
