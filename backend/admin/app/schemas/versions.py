from typing import Any

from app.schemas.common import ApiModel


class ConfigVersionOut(ApiModel):
    id: int
    entityId: int
    version: int
    action: str
    snapshot: dict[str, Any]
    createdAt: str
