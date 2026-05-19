from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.security.jwt import JwtError, decode_token


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    role: str


auth_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> AuthenticatedUser | None:
    settings = get_settings()
    if not settings.jwt_public_key_pem:
        return None
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        token_data = decode_token(credentials.credentials)
    except JwtError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if token_data.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    subject = token_data.get("sub")
    role = token_data.get("role")
    if not subject or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    return AuthenticatedUser(id=str(subject), role=str(role))


def require_auth(user: AuthenticatedUser | None = Depends(get_current_user)) -> AuthenticatedUser | None:
    settings = get_settings()
    if not settings.jwt_public_key_pem:
        return None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user
