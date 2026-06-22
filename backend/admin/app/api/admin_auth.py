from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_admin
from app.db.database import get_connection
from app.schemas.auth import (
    AdminUserOut,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
)
from app.services.auth import authenticate, logout, refresh_tokens

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    with get_connection() as conn:
        return authenticate(conn, payload.username, payload.password)


@router.post("/refresh", response_model=LoginResponse)
def refresh(payload: RefreshRequest) -> LoginResponse:
    with get_connection() as conn:
        return refresh_tokens(conn, payload.refreshToken)


@router.post("/logout")
def logout_route(
    payload: LogoutRequest,
    current_user: AdminUserOut = Depends(get_current_admin),
) -> dict:
    with get_connection() as conn:
        logout(conn, current_user.id, payload.refreshToken)
    return {"ok": True}


@router.get("/me", response_model=AdminUserOut)
def me(current_user: AdminUserOut = Depends(get_current_admin)) -> AdminUserOut:
    if current_user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is unavailable")
    return current_user
