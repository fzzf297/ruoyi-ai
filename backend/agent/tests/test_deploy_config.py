from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]


def _agent_env_names(compose_file: str) -> set[str]:
    compose = yaml.safe_load((ROOT_DIR / compose_file).read_text(encoding="utf-8"))
    values = compose["services"]["agent"]["environment"]
    return {item.split("=", 1)[0] for item in values}


def test_compose_passes_third_party_agent_settings() -> None:
    required = {
        "AGENT_PROJECT_SECRETS",
        "AGENT_THIRD_PARTY_ALLOWED_HOSTS",
        "AGENT_THIRD_PARTY_MAX_RESPONSE_BYTES",
    }
    assert required <= _agent_env_names("docker-compose.yml")
    assert required <= _agent_env_names("docker-compose.prod.yml")
