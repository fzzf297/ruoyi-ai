from typing import Optional

from pydantic import Field

from app.schemas.common import ApiModel


class LoginRequest(ApiModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class RefreshRequest(ApiModel):
    refreshToken: str = Field(..., min_length=1)


class LogoutRequest(ApiModel):
    refreshToken: Optional[str] = None


class AdminUserOut(ApiModel):
    id: int
    username: str
    displayName: str
    status: str
    lastLoginAt: Optional[str] = None
    createdAt: str


class LoginResponse(ApiModel):
    accessToken: str
    refreshToken: str
    tokenType: str = "Bearer"
    expiresIn: int
    user: AdminUserOut
