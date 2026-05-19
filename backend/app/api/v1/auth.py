from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.security.jwt import JwtError, create_access_token, create_refresh_token, decode_token
from app.security.passwords import hash_password, verify_password

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: DbSession) -> TokenResponse:
    settings = get_settings()
    _ensure_jwt_configured(settings)

    user = await _get_user_by_email(session, payload.email)
    if user is None:
        user = await _maybe_bootstrap_admin(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token, _ = create_access_token(str(user.id), role=user.role.value)
    refresh_token, expires_at = create_refresh_token(str(user.id), role=user.role.value)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_at=expires_at)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest) -> TokenResponse:
    settings = get_settings()
    _ensure_jwt_configured(settings)
    try:
        token_data = decode_token(payload.refresh_token)
    except JwtError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if token_data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    subject = str(token_data.get("sub"))
    role = str(token_data.get("role", UserRole.analyst.value))
    access_token, _ = create_access_token(subject, role=role)
    refresh_token, expires_at = create_refresh_token(subject, role=role)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_at=expires_at)


def _ensure_jwt_configured(settings) -> None:
    if not settings.jwt_private_key_pem or not settings.jwt_public_key_pem:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_PRIVATE_KEY_PEM and JWT_PUBLIC_KEY_PEM must be configured",
        )


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _maybe_bootstrap_admin(session: AsyncSession, email: str, password: str) -> User | None:
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return None
    if settings.bootstrap_admin_email.lower() != email.lower():
        return None
    if settings.bootstrap_admin_password != password:
        return None

    existing = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    if existing:
        return None

    user = User(
        email=email.lower(),
        role=UserRole.admin,
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
