import json
import logging
import re
from typing import Any, Optional
from urllib.parse import quote, urlparse

import httpx

from app.core.config import settings
from app.core.errors import AppError
from app.core.project_secrets import get_project_secrets
from app.core.third_party_hosts import extract_hostname, validate_third_party_host
from app.schemas.admin_data import PublicInterfaceOut
from app.services import auth_cache
from app.services.admin_client import admin_client

logger = logging.getLogger(__name__)

ALLOWED_EXECUTE_METHODS = {"GET", "POST"}
PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


async def execute_interface(
    project_code: str,
    interface_code: str,
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    safe_params = params or {}
    project = await admin_client.get_project(project_code)
    base_url = _validate_base_url(project.baseUrl)

    app_interface = await admin_client.get_interface(project_code, interface_code)
    config = await _load_interface_config(project_code, interface_code, app_interface)
    _validate_executable_config(config)

    secrets = get_project_secrets(project_code, settings.project_secrets)
    headers: dict[str, str] = {}
    auth_cache_key: Optional[str] = None
    if config.get("auth", {}).get("useProjectAuth") is True:
        headers, auth_cache_key = await _get_auth_headers(
            project_code, base_url, secrets, config
        )

    data = await _call_with_auth_retry(
        project_code,
        base_url,
        config,
        safe_params,
        secrets,
        headers,
        auth_cache_key,
    )
    extracted = _extract_path(data, config.get("response", {}).get("dataPath", "."))
    return {
        "projectCode": project_code,
        "interfaceCode": interface_code,
        "data": extracted,
    }


async def _call_with_auth_retry(
    project_code: str,
    base_url: str,
    config: dict[str, Any],
    params: dict[str, Any],
    secrets: dict[str, str],
    headers: dict[str, str],
    auth_cache_key: Optional[str],
) -> Any:
    use_project_auth = config.get("auth", {}).get("useProjectAuth") is True
    try:
        return await _call_configured_interface(
            base_url, config, params, secrets, headers
        )
    except AppError as exc:
        if not use_project_auth or exc.message != "THIRD_PARTY_UNAUTHORIZED":
            raise
        if auth_cache_key:
            auth_cache.invalidate(auth_cache_key)
        refreshed, _ = await _get_auth_headers(project_code, base_url, secrets, config)
        return await _call_configured_interface(
            base_url, config, params, secrets, refreshed
        )


async def _load_interface_config(
    project_code: str, interface_code: str, app_interface: PublicInterfaceOut
) -> dict[str, Any]:
    if app_interface.parsedConfig:
        return app_interface.parsedConfig
    config = await admin_client.get_interface_config(project_code, interface_code)
    return config.parsedConfig


def _validate_base_url(base_url: str) -> str:
    value = base_url.strip()
    if not value:
        raise AppError("PROJECT_BASE_URL_REQUIRED", status_code=400)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AppError("PROJECT_BASE_URL_INVALID", status_code=400)
    hostname = extract_hostname(value)
    validate_third_party_host(hostname, settings.third_party_allowed_hosts)
    return value.rstrip("/")


def _validate_executable_config(config: dict[str, Any]) -> None:
    if config.get("kind") != "api":
        raise AppError("INTERFACE_KIND_NOT_API", status_code=400)
    if not isinstance(config.get("readOnly"), bool):
        raise AppError("INTERFACE_READ_ONLY_REQUIRED", status_code=400)
    if config.get("readOnly") is not True:
        raise AppError("INTERFACE_WRITE_NOT_ALLOWED", status_code=400)
    request = config.get("request")
    if not isinstance(request, dict):
        raise AppError("INTERFACE_REQUEST_REQUIRED", status_code=400)
    method = request.get("method")
    if method not in ALLOWED_EXECUTE_METHODS:
        raise AppError("INTERFACE_METHOD_NOT_ALLOWED", status_code=400)
    path = request.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise AppError("INTERFACE_PATH_INVALID", status_code=400)
    for key in ("query", "body", "headers"):
        section = request.get(key)
        if section is not None and not isinstance(section, dict):
            raise AppError("INTERFACE_MAPPING_INVALID", status_code=400)
    _validate_auth_section(config.get("auth"))


def _validate_auth_section(auth: Any) -> None:
    if auth is None:
        return
    if not isinstance(auth, dict):
        raise AppError("AUTH_SECTION_INVALID", status_code=400)
    if "interfaceCode" not in auth:
        return
    interface_code = auth.get("interfaceCode")
    if not isinstance(interface_code, str) or not interface_code.strip():
        raise AppError("AUTH_INTERFACE_CODE_INVALID", status_code=400)


async def _get_auth_headers(
    project_code: str,
    base_url: str,
    secrets: dict[str, str],
    api_config: dict[str, Any],
) -> tuple[dict[str, str], str]:
    auth_config = await _load_project_auth_config(project_code, api_config)
    cache_key = auth_cache.make_cache_key(project_code, base_url, auth_config)

    async def fetch() -> tuple[dict[str, str], Optional[int]]:
        return await _fetch_auth_header(base_url, auth_config, secrets)

    headers = await auth_cache.get_cached_auth_headers(cache_key, project_code, fetch)
    return headers, cache_key


async def _load_project_auth_config(
    project_code: str, api_config: dict[str, Any]
) -> dict[str, Any]:
    auth_section = api_config.get("auth")
    interface_code: Optional[str] = None
    if isinstance(auth_section, dict):
        raw_code = auth_section.get("interfaceCode")
        if isinstance(raw_code, str) and raw_code.strip():
            interface_code = raw_code.strip()

    auth_interfaces: list[tuple[str, dict[str, Any]]] = []
    page = 1
    page_size = 100
    while True:
        result = await admin_client.list_interfaces(
            project_code, page=page, page_size=page_size
        )
        for item in result.items:
            if item.parsedConfig and item.parsedConfig.get("kind") == "auth":
                auth_interfaces.append((item.code, item.parsedConfig))
        if page * page_size >= result.total:
            break
        page += 1

    if interface_code:
        for code, config in auth_interfaces:
            if code == interface_code:
                return config
        raise AppError("PROJECT_AUTH_NOT_FOUND", status_code=400)

    if not auth_interfaces:
        raise AppError("PROJECT_AUTH_NOT_FOUND", status_code=400)
    if len(auth_interfaces) > 1:
        raise AppError("PROJECT_AUTH_NOT_UNIQUE", status_code=400)
    return auth_interfaces[0][1]


async def _fetch_auth_header(
    base_url: str, auth_config: dict[str, Any], secrets: dict[str, str]
) -> tuple[dict[str, str], Optional[int]]:
    response_json = await _request_json(
        base_url, auth_config, params={}, secrets=secrets, headers={}
    )
    response_config = auth_config.get("response", {})
    header_name = _extract_path(response_json, response_config.get("headerNamePath"))
    if not isinstance(header_name, str) or not header_name:
        raise AppError("AUTH_HEADER_NAME_NOT_FOUND", status_code=502)

    header_value_path = response_config.get("headerValuePath")
    if header_value_path:
        header_value = _extract_path(response_json, header_value_path)
    else:
        token = _extract_path(response_json, response_config.get("tokenPath"))
        token_prefix = response_config.get("tokenPrefix", "")
        header_value = f"{token_prefix}{token}"
    if not isinstance(header_value, str) or not header_value:
        raise AppError("AUTH_HEADER_VALUE_NOT_FOUND", status_code=502)

    expires_in_path = response_config.get("expiresInPath")
    expires_in: Optional[int] = None
    if isinstance(expires_in_path, str) and expires_in_path:
        try:
            raw = _extract_path(response_json, expires_in_path)
            if isinstance(raw, int):
                expires_in = raw
        except AppError:
            expires_in = None
    return {header_name: header_value}, expires_in


async def _call_configured_interface(
    base_url: str,
    config: dict[str, Any],
    params: dict[str, Any],
    secrets: dict[str, str],
    headers: dict[str, str],
) -> Any:
    return await _request_json(base_url, config, params, secrets, headers=headers)


async def _read_limited_response(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    limit = settings.third_party_max_response_bytes
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > limit:
            raise AppError("THIRD_PARTY_RESPONSE_TOO_LARGE", status_code=502)
        chunks.append(chunk)
    return b"".join(chunks)


async def _request_json(
    base_url: str,
    config: dict[str, Any],
    params: dict[str, Any],
    secrets: dict[str, str],
    headers: dict[str, str],
) -> Any:
    request = config["request"]
    method = request["method"]
    path = _render_path_template(request["path"], params)
    url = base_url + path
    query = _render_mapping(request.get("query", {}), params, secrets)
    body = _render_mapping(request.get("body", {}), params, secrets)
    configured_headers = _render_mapping(request.get("headers", {}), params, secrets)
    request_headers = {str(key): str(value) for key, value in configured_headers.items()}
    request_headers.update(headers)
    content_type = request.get("contentType")
    kwargs: dict[str, Any] = {"params": query or None, "headers": request_headers}
    if method == "POST":
        if content_type == "application/x-www-form-urlencoded":
            request_headers["Content-Type"] = content_type
            kwargs["data"] = body
        elif body:
            kwargs["json"] = body
    try:
        async with httpx.AsyncClient(timeout=settings.admin_timeout) as client:
            async with client.stream(method, url, **kwargs) as response:
                if response.status_code == 401:
                    logger.warning(
                        "third-party unauthorized: method=%s path=%s", method, path
                    )
                    raise AppError("THIRD_PARTY_UNAUTHORIZED", status_code=401)
                if response.status_code >= 400:
                    logger.warning(
                        "third-party api error: method=%s path=%s status=%s",
                        method,
                        path,
                        response.status_code,
                    )
                    raise AppError(
                        f"THIRD_PARTY_API_ERROR: {response.status_code}",
                        status_code=502,
                    )
                content = await _read_limited_response(response)
    except httpx.TimeoutException as exc:
        logger.warning("third-party request timeout: method=%s path=%s", method, path)
        raise AppError("THIRD_PARTY_TIMEOUT", status_code=504) from exc
    except httpx.HTTPError as exc:
        logger.warning("third-party request failed: method=%s path=%s", method, path)
        raise AppError("THIRD_PARTY_UNREACHABLE", status_code=503) from exc

    try:
        return json.loads(content)
    except ValueError as exc:
        logger.warning("third-party non-json response: method=%s path=%s", method, path)
        raise AppError("THIRD_PARTY_RESPONSE_NOT_JSON", status_code=502) from exc


def _render_path_template(path_template: str, params: dict[str, Any]) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name.startswith("secret."):
            raise AppError("INTERFACE_PATH_SECRET_NOT_ALLOWED", status_code=400)
        if name not in params:
            raise AppError(f"INTERFACE_PARAM_REQUIRED: {name}", status_code=400)
        return quote(str(params[name]), safe="")

    return PLACEHOLDER_RE.sub(replace, path_template)


def _render_mapping(
    value: Any, params: dict[str, Any], secrets: dict[str, str]
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise AppError("INTERFACE_MAPPING_INVALID", status_code=400)
    return {
        str(key): _render_value(item, params, secrets) for key, item in value.items()
    }


def _render_value(value: Any, params: dict[str, Any], secrets: dict[str, str]) -> Any:
    if isinstance(value, str):
        matches = PLACEHOLDER_RE.findall(value)
        if len(matches) == 1 and value == "{" + matches[0] + "}":
            return _resolve_placeholder(matches[0], params, secrets)
        return _render_template(value, params, secrets)
    if isinstance(value, dict):
        return _render_mapping(value, params, secrets)
    if isinstance(value, list):
        return [_render_value(item, params, secrets) for item in value]
    return value


def _render_template(value: str, params: dict[str, Any], secrets: dict[str, str]) -> str:
    def replace(match: re.Match) -> str:
        resolved = _resolve_placeholder(match.group(1), params, secrets)
        return str(resolved)

    return PLACEHOLDER_RE.sub(replace, value)


def _resolve_placeholder(name: str, params: dict[str, Any], secrets: dict[str, str]) -> Any:
    if name.startswith("secret."):
        key = name[7:]
        if key not in secrets:
            raise AppError(f"PROJECT_SECRET_REQUIRED: {key}", status_code=400)
        return secrets[key]
    if name not in params:
        raise AppError(f"INTERFACE_PARAM_REQUIRED: {name}", status_code=400)
    return params[name]


def _extract_path(data: Any, path: Optional[str]) -> Any:
    if path in (None, "", "."):
        return data
    current = data
    for part in str(path).split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise AppError(f"RESPONSE_PATH_NOT_FOUND: {path}", status_code=502)
    return current
