from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Status

T = TypeVar("T")


class ApiModel(BaseModel):
    model_config = ConfigDict(validate_by_name=True, use_enum_values=True)


class ListResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    pageSize: int


class StatusPatch(ApiModel):
    status: Status = Field(..., description="enabled or disabled")
