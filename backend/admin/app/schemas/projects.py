from typing import Optional

from pydantic import Field, field_validator

from app.models.enums import Status
from app.schemas.common import ApiModel


class ProjectCreate(ApiModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    status: Status = Status.enabled

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", value):
            raise ValueError(
                "code must start with a letter and contain only letters, digits, _ or -"
            )
        return value


class ProjectUpdate(ApiModel):
    code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    status: Optional[Status] = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        import re

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", value):
            raise ValueError(
                "code must start with a letter and contain only letters, digits, _ or -"
            )
        return value


class ProjectOut(ApiModel):
    id: int
    code: str
    name: str
    description: str
    status: str
    createdAt: str
    updatedAt: str
