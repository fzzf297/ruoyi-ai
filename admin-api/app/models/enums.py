from enum import Enum


class Status(str, Enum):
    enabled = "enabled"
    disabled = "disabled"


class AdminStatus(str, Enum):
    active = "active"
    disabled = "disabled"


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class AuthMode(str, Enum):
    none = "none"
    bearer = "bearer"
    api_key = "api_key"
    signature = "signature"
