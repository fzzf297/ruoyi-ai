import pytest

from app.core import third_party_hosts
from app.core.errors import AppError
from app.core.third_party_hosts import validate_third_party_host


@pytest.mark.parametrize(
    ("host", "allowed"),
    [
        ("localhost", []),
        ("127.0.0.1", []),
        ("10.0.0.1", []),
        ("192.168.1.1", []),
        ("169.254.169.254", []),
        ("metadata.google.internal", []),
    ],
)
def test_validate_third_party_host_blocks_unsafe_hosts(host: str, allowed: list[str]) -> None:
    with pytest.raises(AppError) as exc_info:
        validate_third_party_host(host, allowed)
    assert exc_info.value.message == "THIRD_PARTY_HOST_NOT_ALLOWED"


def test_validate_third_party_host_blocks_allowlisted_loopback_ip() -> None:
    with pytest.raises(AppError) as exc_info:
        validate_third_party_host("127.0.0.1", ["127.0.0.1"])
    assert exc_info.value.message == "THIRD_PARTY_HOST_NOT_ALLOWED"


def test_validate_third_party_host_allows_docker_internal_when_allowlisted() -> None:
    validate_third_party_host("host.docker.internal", ["host.docker.internal"])


def test_validate_third_party_host_blocks_docker_internal_without_allowlist() -> None:
    with pytest.raises(AppError) as exc_info:
        validate_third_party_host("host.docker.internal", [])
    assert exc_info.value.message == "THIRD_PARTY_HOST_NOT_ALLOWED"


def test_validate_third_party_host_allows_public_hostname_when_allowlist_empty(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        third_party_hosts,
        "socket",
        _fake_socket("93.184.216.34"),
        raising=False,
    )
    validate_third_party_host("example.com", [])


def test_validate_third_party_host_blocks_hostname_resolving_to_private_ip(
    monkeypatch,
) -> None:
    monkeypatch.setattr(third_party_hosts, "socket", _fake_socket("10.0.0.5"), raising=False)
    with pytest.raises(AppError) as exc_info:
        validate_third_party_host("example.com", [])
    assert exc_info.value.message == "THIRD_PARTY_HOST_NOT_ALLOWED"


def test_validate_third_party_host_enforces_allowlist() -> None:
    validate_third_party_host("allowed.example", ["allowed.example"])
    with pytest.raises(AppError) as exc_info:
        validate_third_party_host("other.example", ["allowed.example"])
    assert exc_info.value.message == "THIRD_PARTY_HOST_NOT_ALLOWED"


def _fake_socket(ip_address: str):
    class FakeSocket:
        @staticmethod
        def getaddrinfo(*args, **kwargs):
            return [(None, None, None, "", (ip_address, 0))]

    return FakeSocket
