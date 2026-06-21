from fastapi import Depends, Header, HTTPException, status

from app.core.security import decode_token
from app.db.database import get_connection
from app.repositories.users import get_user_by_id
from app.schemas.auth import AdminUserOut


def get_current_admin(authorization: str = Header(default="")) -> AdminUserOut:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token, expected_type="access")
    user_id = int(payload["sub"])

    with get_connection() as conn:
        user = get_user_by_id(conn, user_id)

    if user is None or user["status"] != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is unavailable")

    return AdminUserOut(
        id=user["id"],
        username=user["username"],
        displayName=user["display_name"],
        status=user["status"],
        lastLoginAt=user["last_login_at"],
        createdAt=user["created_at"],
    )


CurrentAdmin = Depends(get_current_admin)
