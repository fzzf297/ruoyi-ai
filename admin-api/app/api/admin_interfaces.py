from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_admin
from app.db.database import get_connection
from app.schemas.auth import AdminUserOut
from app.schemas.common import ListResponse, StatusPatch
from app.schemas.interfaces import (
    InterfaceConfigOut,
    InterfaceCreate,
    InterfaceOut,
    InterfaceUpdate,
    YamlConfigIn,
    YamlValidationOut,
)
from app.schemas.versions import ConfigVersionOut
from app.services.interfaces import (
    create_interface,
    delete_interface,
    get_interface,
    get_interface_config,
    get_interface_version,
    list_interface_versions,
    list_interfaces,
    update_interface,
    update_interface_config,
    update_interface_status,
    validate_yaml_config,
)

router = APIRouter()


@router.get("/projects/{project_id}/interfaces", response_model=ListResponse[InterfaceOut])
def list_interfaces_route(
    project_id: int,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    keyword: str = "",
    _: AdminUserOut = Depends(get_current_admin),
) -> ListResponse[InterfaceOut]:
    with get_connection() as conn:
        return list_interfaces(conn, project_id, page, pageSize, keyword, include_disabled=True)


@router.post(
    "/projects/{project_id}/interfaces",
    response_model=InterfaceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_interface_route(
    project_id: int,
    payload: InterfaceCreate,
    _: AdminUserOut = Depends(get_current_admin),
) -> InterfaceOut:
    with get_connection() as conn:
        return create_interface(conn, project_id, payload)


@router.get("/interfaces/{interface_id}", response_model=InterfaceOut)
def get_interface_route(
    interface_id: int,
    _: AdminUserOut = Depends(get_current_admin),
) -> InterfaceOut:
    with get_connection() as conn:
        return get_interface(conn, interface_id)


@router.put("/interfaces/{interface_id}", response_model=InterfaceOut)
def update_interface_route(
    interface_id: int,
    payload: InterfaceUpdate,
    _: AdminUserOut = Depends(get_current_admin),
) -> InterfaceOut:
    with get_connection() as conn:
        return update_interface(conn, interface_id, payload)


@router.patch("/interfaces/{interface_id}/status", response_model=InterfaceOut)
def update_interface_status_route(
    interface_id: int,
    payload: StatusPatch,
    _: AdminUserOut = Depends(get_current_admin),
) -> InterfaceOut:
    with get_connection() as conn:
        return update_interface_status(conn, interface_id, payload.status)


@router.delete("/interfaces/{interface_id}")
def delete_interface_route(
    interface_id: int,
    _: AdminUserOut = Depends(get_current_admin),
) -> dict:
    with get_connection() as conn:
        delete_interface(conn, interface_id)
    return {"ok": True}


@router.get("/interfaces/{interface_id}/config", response_model=InterfaceConfigOut)
def get_interface_config_route(
    interface_id: int,
    _: AdminUserOut = Depends(get_current_admin),
) -> InterfaceConfigOut:
    with get_connection() as conn:
        return get_interface_config(conn, interface_id)


@router.put("/interfaces/{interface_id}/config-yaml", response_model=InterfaceConfigOut)
def update_interface_config_route(
    interface_id: int,
    payload: YamlConfigIn,
    _: AdminUserOut = Depends(get_current_admin),
) -> InterfaceConfigOut:
    with get_connection() as conn:
        return update_interface_config(conn, interface_id, payload.yamlText)


@router.post("/interfaces/config-yaml/validate", response_model=YamlValidationOut)
def validate_yaml_route(
    payload: YamlConfigIn,
    _: AdminUserOut = Depends(get_current_admin),
) -> YamlValidationOut:
    parsed = validate_yaml_config(payload.yamlText)
    return YamlValidationOut(valid=True, parsedConfig=parsed, errors=[])


@router.get("/interfaces/{interface_id}/versions", response_model=ListResponse[ConfigVersionOut])
def list_interface_versions_route(
    interface_id: int,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    _: AdminUserOut = Depends(get_current_admin),
) -> ListResponse[ConfigVersionOut]:
    with get_connection() as conn:
        return list_interface_versions(conn, interface_id, page, pageSize)


@router.get("/interfaces/{interface_id}/versions/{version}", response_model=ConfigVersionOut)
def get_interface_version_route(
    interface_id: int,
    version: int,
    _: AdminUserOut = Depends(get_current_admin),
) -> ConfigVersionOut:
    with get_connection() as conn:
        return get_interface_version(conn, interface_id, version)
