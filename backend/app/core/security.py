from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt
from fastapi import Response
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import get_settings
from app.core.enums import StudioRole
from app.core.exceptions import UnauthorizedError
from app.core.timezone import utcnow

password_hasher = PasswordHash((Argon2Hasher(),))
# Hash Argon2id pré-calculado para mitigação de timing-attack quando e-mail não existe
_DUMMY_PASSWORD_HASH = password_hasher.hash("dummy_constant_time_mitigation_password")


def hash_password(plain_password: str) -> str:
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    if not hashed_password:
        password_hasher.verify(plain_password, _DUMMY_PASSWORD_HASH)
        return False
    return password_hasher.verify(plain_password, hashed_password)


def generate_refresh_token_raw() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: uuid.UUID,
    studio_id: uuid.UUID | None,
    role: StudioRole | None,
    is_superadmin: bool,
    enabled_modules: list[str] | None = None,
) -> tuple[str, int]:
    settings = get_settings()
    now = utcnow()
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "studio_id": str(studio_id) if studio_id else None,
        "role": role.value if role else None,
        "is_superadmin": is_superadmin,
        "modules": enabled_modules or [],
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    encoded = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded, int(expires_delta.total_seconds())


def create_studio_selection_token(*, user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = utcnow()
    expire = now + timedelta(minutes=settings.STUDIO_SELECTION_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "studio_selection",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_jwt_token(token: str, *, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError(detail="Sessão expirada.", code="TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(detail="Token inválido.", code="INVALID_TOKEN") from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError(detail="Tipo de token inválido.", code="INVALID_TOKEN_TYPE")
    return payload


def refresh_token_expires_at() -> datetime:
    settings = get_settings()
    return utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    settings = get_settings()
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=f"{settings.API_V1_PREFIX}/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=f"{settings.API_V1_PREFIX}/auth",
    )
