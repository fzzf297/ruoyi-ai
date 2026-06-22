import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import HTTPException, status

from app.core.config import settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    rounds = 260_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, rounds_text, salt_text, digest_text = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_text)
        salt = _b64url_decode(salt_text)
        expected = _b64url_decode(digest_text)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(actual, expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(subject: int, token_type: str, expires_in_seconds: int) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_in_seconds,
        "jti": secrets.token_urlsafe(16),
    }
    signing_input = "{}.{}".format(
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    )
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    signing_input = f"{header_part}.{payload_part}"
    expected_signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        signature = _b64url_decode(signature_part)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload
