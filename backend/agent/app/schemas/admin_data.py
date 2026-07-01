from typing import Any, Optional

from app.schemas.common import ApiModel


class ProjectOut(ApiModel):
    id: int
    code: str
    name: str
    description: str
    baseUrl: str
    status: str
    createdAt: str
    updatedAt: str


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


class PublicInterfaceOut(InterfaceOut):
    parsedConfig: Optional[dict[str, Any]] = None


class InterfaceConfigOut(ApiModel):
    interfaceId: int
    yamlText: str
    parsedConfig: dict[str, Any]
    createdAt: str
    updatedAt: str


class ConfigVersionOut(ApiModel):
    id: int
    entityId: int
    version: int
    action: str
    snapshot: dict[str, Any]
    createdAt: str
