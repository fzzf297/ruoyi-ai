import os
from dataclasses import dataclass
from pathlib import Path

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
    secret_key: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    login_max_attempts: int
    login_lock_minutes: int
    cors_origins: list[str]
    default_admin_username: str
    default_admin_password: str
    default_admin_display_name: str


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("ADMIN_API_APP_NAME", "Admin API"),
        environment=os.getenv("ADMIN_API_ENV", "local"),
        database_url=_resolve_database_url(
            os.getenv("ADMIN_API_DATABASE_URL", "sqlite:///data/admin-api.db")
        ),
        secret_key=os.getenv("ADMIN_API_SECRET_KEY", "change-me-in-production"),
        access_token_expire_minutes=int(os.getenv("ADMIN_API_ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        refresh_token_expire_days=int(os.getenv("ADMIN_API_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
        login_max_attempts=int(os.getenv("ADMIN_API_LOGIN_MAX_ATTEMPTS", "5")),
        login_lock_minutes=int(os.getenv("ADMIN_API_LOGIN_LOCK_MINUTES", "15")),
        cors_origins=_csv(os.getenv("ADMIN_API_CORS_ORIGINS", "*")) or ["*"],
        default_admin_username=os.getenv("ADMIN_API_DEFAULT_ADMIN_USERNAME", "admin"),
        default_admin_password=os.getenv("ADMIN_API_DEFAULT_ADMIN_PASSWORD", "admin123"),
        default_admin_display_name=os.getenv(
            "ADMIN_API_DEFAULT_ADMIN_DISPLAY_NAME", "Administrator"
        ),
    )


settings = load_settings()
