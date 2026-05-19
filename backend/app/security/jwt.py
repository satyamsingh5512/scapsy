from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import get_settings


class JwtError(Exception):
    pass


def create_access_token(subject: str, *, role: str) -> tuple[str, datetime]:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_ttl_minutes)
    payload = _base_payload(subject, role=role, token_type="access", expires_at=expires_at)
    return _encode(payload), expires_at


def create_refresh_token(subject: str, *, role: str) -> tuple[str, datetime]:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_ttl_days)
    payload = _base_payload(subject, role=role, token_type="refresh", expires_at=expires_at)
    return _encode(payload), expires_at


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.jwt_public_key_pem:
        raise JwtError("JWT public key is not configured")
    try:
        return jwt.decode(
            token,
            settings.jwt_public_key_pem,
            algorithms=["RS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise JwtError(str(exc)) from exc


def _base_payload(subject: str, *, role: str, token_type: str, expires_at: datetime) -> dict[str, Any]:
    settings = get_settings()
    return {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expires_at.timestamp()),
    }


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    if not settings.jwt_private_key_pem:
        raise JwtError("JWT private key is not configured")
    return jwt.encode(payload, settings.jwt_private_key_pem, algorithm="RS256")
