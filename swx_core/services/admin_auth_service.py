from typing import Any

from fastapi import HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.core.jwt import create_token, TokenAudience
from swx_core.config.settings import settings
from swx_core.models.admin_user import AdminUser
from swx_core.models.token import Token, TokenRefreshRequest
from swx_core.repositories.admin_user_repository import authenticate_admin, get_admin_by_email
from swx_core.security.refresh_token_service import (
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
)
from swx_core.services.settings_helper import get_token_expiration


async def login_admin_service(
    session: AsyncSession, form_data: OAuth2PasswordRequestForm, request: Request | None = None
) -> Token:
    admin_user = await authenticate_admin(
        session=session, email=form_data.username, password=form_data.password
    )
    if not admin_user:
        raise HTTPException(status_code=401, detail="Incorrect admin email or password")
    if not admin_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive admin user")

    return await _create_admin_token_pair(session, admin_user.email)


async def refresh_admin_token_service(
    session: AsyncSession, request_data: TokenRefreshRequest, request: Request
) -> Token:
    result = await verify_refresh_token(session, request_data.refresh_token, request)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    email, auth_provider = result
    await _require_active_admin(session, email)

    return await _create_admin_token_pair(session, email, auth_provider)


async def logout_admin_service(
    session: AsyncSession, request_data: TokenRefreshRequest, request: Request
) -> dict[str, Any]:
    result = await verify_refresh_token(session, request_data.refresh_token, request)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    await revoke_refresh_token(session, request_data.refresh_token)
    return {"message": "Admin logged out successfully"}


async def verify_admin_cookie_refresh(
    session: AsyncSession, refresh_token: str, request: Request
) -> tuple[AdminUser, str, str]:
    """Verify a refresh token from a cookie and confirm it belongs to an active admin.

    Returns (admin_user, email, auth_provider). Raises HTTPException on failure.
    """
    result = await verify_refresh_token(session, refresh_token, request)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    email, auth_provider = result
    admin_user = await _require_active_admin(session, email)

    return admin_user, email, auth_provider


async def _create_admin_token_pair(
    session: AsyncSession, email: str, auth_provider: str = "local"
) -> Token:
    access_expires = await get_token_expiration(session, "access")
    refresh_expires = await get_token_expiration(session, "refresh")

    access_token = create_token(email, TokenAudience.ADMIN, expires_delta=access_expires)
    refresh_token = await create_refresh_token(
        session, email, expires_delta=refresh_expires, auth_provider=auth_provider
    )

    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


async def _require_active_admin(session: AsyncSession, email: str) -> AdminUser:
    admin_user = await get_admin_by_email(session=session, email=email)
    if not admin_user:
        raise HTTPException(status_code=401, detail="Admin user not found")
    if not admin_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive admin user")
    return admin_user


def set_auth_cookies(response, access_token: str, refresh_token: str, access_max_age: int, refresh_max_age: int):
    secure = settings.COOKIE_SECURE and settings.ENVIRONMENT != "local"
    samesite = settings.COOKIE_SAMESITE
    domain = settings.COOKIE_DOMAIN

    response.set_cookie(
        key=settings.COOKIE_ACCESS_TOKEN_NAME,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=access_max_age,
        path="/",
        domain=domain,
    )
    response.set_cookie(
        key=settings.COOKIE_REFRESH_TOKEN_NAME,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=refresh_max_age,
        path="/api",
        domain=domain,
    )


def clear_auth_cookies(response):
    response.delete_cookie(key=settings.COOKIE_ACCESS_TOKEN_NAME, path="/", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(key=settings.COOKIE_REFRESH_TOKEN_NAME, path="/api", domain=settings.COOKIE_DOMAIN)