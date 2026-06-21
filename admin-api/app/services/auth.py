import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import create_token, decode_token, token_hash, verify_password
from app.repositories.users import get_user_by_id, get_user_by_username
from app.schemas.auth import AdminUserOut, LoginResponse


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _user_out(row: sqlite3.Row) -> AdminUserOut:
    return AdminUserOut(
        id=row["id"],
        username=row["username"],
        displayName=row["display_name"],
        status=row["status"],
        lastLoginAt=row["last_login_at"],
        createdAt=row["created_at"],
    )


def _issue_tokens(conn: sqlite3.Connection, row: sqlite3.Row) -> LoginResponse:
    access_expires = settings.access_token_expire_minutes * 60
    refresh_expires_at = _now() + timedelta(days=settings.refresh_token_expire_days)
    access_token = create_token(row["id"], "access", access_expires)
    refresh_token = create_token(
        row["id"],
        "refresh",
        settings.refresh_token_expire_days * 24 * 60 * 60,
    )
    conn.execute(
        """
        INSERT INTO refresh_tokens(user_id, token_hash, expires_at)
        VALUES (?, ?, ?)
        """,
        (row["id"], token_hash(refresh_token), _iso(refresh_expires_at)),
    )
    return LoginResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        expiresIn=access_expires,
        user=_user_out(row),
    )


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> LoginResponse:
    user = get_user_by_username(conn, username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user["status"] != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")

    locked_until = user["locked_until"]
    if locked_until and _dt(locked_until) > _now():
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="User is temporarily locked")

    if not verify_password(password, user["password_hash"]):
        failed_count = int(user["failed_login_count"]) + 1
        locked = None
        if failed_count >= settings.login_max_attempts:
            locked = _iso(_now() + timedelta(minutes=settings.login_lock_minutes))
        conn.execute(
            """
            UPDATE admin_users
            SET failed_login_count = ?, locked_until = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (failed_count, locked, user["id"]),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    conn.execute(
        """
        UPDATE admin_users
        SET failed_login_count = 0,
            locked_until = NULL,
            last_login_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (user["id"],),
    )
    fresh_user = get_user_by_id(conn, user["id"])
    return _issue_tokens(conn, fresh_user)


def refresh_tokens(conn: sqlite3.Connection, refresh_token: str) -> LoginResponse:
    payload = decode_token(refresh_token, expected_type="refresh")
    user_id = int(payload["sub"])
    refresh = conn.execute(
        """
        SELECT * FROM refresh_tokens
        WHERE user_id = ? AND token_hash = ? AND revoked_at IS NULL
        """,
        (user_id, token_hash(refresh_token)),
    ).fetchone()
    if refresh is None or _dt(refresh["expires_at"]) <= _now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired"
        )
    user = get_user_by_id(conn, user_id)
    if user is None or user["status"] != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is unavailable")
    conn.execute(
        "UPDATE refresh_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE id = ?",
        (refresh["id"],),
    )
    return _issue_tokens(conn, user)


def logout(conn: sqlite3.Connection, user_id: int, refresh_token: Optional[str]) -> None:
    if refresh_token:
        conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND token_hash = ? AND revoked_at IS NULL
            """,
            (user_id, token_hash(refresh_token)),
        )
        return
    conn.execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND revoked_at IS NULL
        """,
        (user_id,),
    )
