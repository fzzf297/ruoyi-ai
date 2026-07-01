import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS = 300
_SKEW_SECONDS = 30

_cache: dict[str, tuple[dict[str, str], float]] = {}


def make_cache_key(project_code: str, base_url: str, auth_config: dict[str, Any]) -> str:
    payload = json.dumps(auth_config, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{project_code}|{base_url}|{fingerprint}"


def invalidate(cache_key: str) -> None:
    _cache.pop(cache_key, None)


def clear() -> None:
    _cache.clear()


async def get_cached_auth_headers(
    cache_key: str,
    project_code: str,
    fetch: Callable[[], Awaitable[tuple[dict[str, str], Optional[int]]]],
) -> dict[str, str]:
    now = time.time()
    cached = _cache.get(cache_key)
    if cached is not None and cached[1] > now:
        return dict(cached[0])

    headers, expires_in = await fetch()
    ttl = expires_in if expires_in and expires_in > 0 else _DEFAULT_TTL_SECONDS
    _cache[cache_key] = (dict(headers), now + max(ttl - _SKEW_SECONDS, 1))
    logger.info("auth cache refreshed: project=%s key=%s ttl=%s", project_code, cache_key, ttl)
    return headers
