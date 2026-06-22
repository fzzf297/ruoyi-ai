from typing import Any, Optional

from pydantic import Field, field_validator

from app.models.enums import AuthMode, HttpMethod, Status
from app.schemas.common import ApiModel


class InterfaceCreate(ApiModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    method: HttpMethod
    path: str = Field(..., min_length=1, max_length=240)
    authMode: AuthMode = AuthMode.none
    status: Status = Status.enabled
    description: str = Field(default="", max_length=500)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", value):
            raise ValueError(
                "code must start with a letter and contain only letters, digits, _ or -"
            )
        return value

    @field_validator("path")
    @classmethod
    def path_must_start_with_slash(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("path must start with /")
        return value


class InterfaceUpdate(ApiModel):
    code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    method: Optional[HttpMethod] = None
    path: Optional[str] = Field(default=None, min_length=1, max_length=240)
    authMode: Optional[AuthMode] = None
    status: Optional[Status] = None
    description: Optional[str] = Field(default=None, max_length=500)

    @field_validator("path")
    @classmethod
    def path_must_start_with_slash(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.startswith("/"):
            raise ValueError("path must start with /")
        return value


class InterfaceOut(ApiModel):
    id: int
    projectId: int
    code: str
    name: str
    method: str
    path: str
    authMode: str
    status: str
    description: str
    createdAt: str
    updatedAt: str


class YamlConfigIn(ApiModel):
    yamlText: str = Field(..., min_length=1)


class YamlValidationOut(ApiModel):
    valid: bool
    parsedConfig: dict[str, Any]
    errors: list


class InterfaceConfigOut(ApiModel):
    interfaceId: int
    yamlText: str
    parsedConfig: dict[str, Any]
    createdAt: str
    updatedAt: str


class PublicInterfaceOut(InterfaceOut):
    parsedConfig: Optional[dict[str, Any]] = None
