import json
import os
import re


def _env_key_to_secret_name(suffix: str) -> str:
    parts = suffix.lower().split("_")
    if not parts:
        return suffix
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def load_all_project_secrets() -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    raw = os.getenv("AGENT_PROJECT_SECRETS", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            for project_code, secrets in parsed.items():
                if isinstance(project_code, str) and isinstance(secrets, dict):
                    merged[project_code] = {
                        str(key): str(value)
                        for key, value in secrets.items()
                        if value is not None and str(value) != ""
                    }

    # AGENT_PROJECT_RUOYI_CLASSIC__CLIENT_ID -> project ruoyi-classic, secret clientId
    pattern = re.compile(r"^AGENT_PROJECT_(.+?)__(.+)$")
    for key, value in os.environ.items():
        if not value:
            continue
        match = pattern.match(key)
        if not match:
            continue
        project_code = match.group(1).lower().replace("_", "-")
        secret_name = _env_key_to_secret_name(match.group(2))
        merged.setdefault(project_code, {})[secret_name] = value
    return merged


def get_project_secrets(
    project_code: str, all_secrets: dict[str, dict[str, str]]
) -> dict[str, str]:
    return dict(all_secrets.get(project_code, {}))
