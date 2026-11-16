"""Password hashing and JWT issuing.

bcrypt directly rather than passlib: passlib is unmaintained and its bcrypt
backend breaks on bcrypt 4.x. The 72-byte truncation is handled explicitly
because silently truncating a password is a real (if minor) security bug.
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings

settings = get_settings()

_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a password. Rejects rather than truncates anything over 72 bytes."""
    encoded = password.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        raise ValueError(
            "Password is longer than 72 bytes, which bcrypt cannot store. "
            "Use a shorter password or a passphrase under 72 characters."
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check. Returns False on any malformed hash rather than raising."""
    try:
        encoded = password.encode("utf-8")
        if len(encoded) > _BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(encoded, password_hash.encode())
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str) -> tuple[str, int]:
    """Return (token, ttl_seconds)."""
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "typ": "access",
    }
    token = jwt.encode(payload, settings.resolved_jwt_secret(), algorithm=settings.jwt_algorithm)
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> str | None:
    """Return the user id, or None if the token is invalid, expired or the wrong type."""
    try:
        payload = jwt.decode(
            token,
            settings.resolved_jwt_secret(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "access":
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())
