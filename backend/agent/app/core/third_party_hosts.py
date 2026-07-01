import ipaddress
import socket

from app.core.errors import AppError

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.google",
    }
)

_ALLOWLIST_ONLY_HOSTNAMES = frozenset(
    {
        "host.docker.internal",
    }
)


def extract_hostname(base_url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(base_url)
    hostname = parsed.hostname
    if not hostname:
        raise AppError("PROJECT_BASE_URL_INVALID", status_code=400)
    return hostname.lower()


def _is_hard_blocked_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def _resolved_addresses(hostname: str) -> list[str]:
    try:
        results = socket.getaddrinfo(hostname, None)
    except OSError:
        return []
    addresses = []
    for result in results:
        sockaddr = result[4]
        if sockaddr:
            addresses.append(str(sockaddr[0]))
    return addresses


def _raise_not_allowed() -> None:
    raise AppError("THIRD_PARTY_HOST_NOT_ALLOWED", status_code=400)


def validate_third_party_host(hostname: str, allowed_hosts: list[str]) -> None:
    host = hostname.lower()
    allowed = {item.lower() for item in allowed_hosts}

    if host in _BLOCKED_HOSTNAMES or _is_hard_blocked_ip(host):
        _raise_not_allowed()

    if host in _ALLOWLIST_ONLY_HOSTNAMES:
        if host not in allowed:
            _raise_not_allowed()
        return

    if allowed_hosts and host not in allowed:
        _raise_not_allowed()

    for address in _resolved_addresses(host):
        if _is_hard_blocked_ip(address):
            _raise_not_allowed()
