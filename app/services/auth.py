"""
JWT auth helpers — password hashing, token creation, token decoding.

Uses Python's built-in hashlib.pbkdf2_hmac for password hashing
(passlib's bcrypt backend crashes on Python 3.14 at import time).
"""

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7
_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return base64.b64encode(salt + key).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        decoded = base64.b64decode(hashed.encode())
        salt, stored = decoded[:32], decoded[32:]
        key = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, _ITERATIONS)
        return hmac.compare_digest(key, stored)
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """Decode a JWT and return the subject (email). Raises 401 on failure."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if not email:
            raise credentials_exc
        return email
    except JWTError:
        raise credentials_exc
