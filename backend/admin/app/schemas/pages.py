from typing import Any, Optional

from pydantic import Field, field_validator

from app.models.enums import Status
from app.schemas.common import ApiModel


class PageCreate(ApiModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    route: str = Field(..., min_length=1, max_length=240)
    sortOrder: int = Field(default=0, ge=0)
    status: Status = Status.enabled
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", value):
            raise ValueError(
                "code must start with a letter and contain only letters, digits, _ or -"
            )
        return value

    @field_validator("route")
    @classmethod
    def route_must_start_with_slash(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("route must start with /")
        return value


class PageUpdate(ApiModel):
    code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    route: Optional[str] = Field(default=None, min_length=1, max_length=240)
    sortOrder: Optional[int] = Field(default=None, ge=0)
    status: Optional[Status] = None
    config: Optional[dict[str, Any]] = None

    @field_validator("route")
    @classmethod
    def route_must_start_with_slash(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.startswith("/"):
            raise ValueError("route must start with /")
        return value


class PageOut(ApiModel):
    id: int
    projectId: int
    code: str
    name: str
    route: str
    sortOrder: int
    status: str
    config: dict[str, Any]
    createdAt: str
    updatedAt: str
