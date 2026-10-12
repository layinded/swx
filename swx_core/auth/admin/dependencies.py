"""
Admin Authentication Dependencies
---------------------------------
This module provides FastAPI dependencies for admin authentication.

Admin users authenticate separately from regular users and use tokens
with audience="admin".

Supports both:
- Authorization: Bearer header (for API clients)
- httpOnly cookie (for browser-based apps using BFF pattern)
"""

from typing import Annotated, Any
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.auth.core.jwt import decode_token, TokenAudience
from swx_core.auth.core.bearer_or_cookie import BearerOrCookieAuth
from swx_core.auth.auth_cache import admin_auth_cache
from swx_core.config.settings import settings
from swx_core.database.db import SessionDep
from swx_core.models.admin_user import AdminUser
from swx_core.utils.language_helper import translate
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType

# Bearer or Cookie authentication for admin endpoints (BFF pattern)
admin_auth = BearerOrCookieAuth()
AdminTokenDep = Annotated[HTTPAuthorizationCredentials | None, Depends(admin_auth)]

_ADMIN_CACHE_FIELDS = (
    "id", "email", "full_name", "is_active", "auth_provider", "provider_id", "created_at",
)


def _admin_to_cache_dict(admin: AdminUser) -> dict[str, Any]:
    return {field: getattr(admin, field) for field in _ADMIN_CACHE_FIELDS}


def _cache_dict_to_admin(data: dict[str, Any]) -> AdminUser:
    return AdminUser(**data)


async def get_current_admin_user(
    session: SessionDep,
    token: AdminTokenDep,
    request: Request,
) -> AdminUser:
    """Retrieves and validates the currently authenticated admin user.

    This function:
    1. Validates the JWT token with audience="admin"
    2. Checks token scopes (if any)
    3. Retrieves the admin user from L1/L2 cache or database
    4. Validates the admin user is active

    Supports token from:
    - Authorization: Bearer header (API clients)
    - httpOnly cookie (browser-based apps)

    Args:
        session: Database session (AsyncSession).
        token: JWT token from request header or cookie.
        request: HTTP request object.

    Returns:
        AdminUser: The authenticated admin user.

    Raises:
        HTTPException (401): If token is invalid, expired, or wrong audience.
        HTTPException (404): If admin user not found.
        HTTPException (400): If admin account is inactive.
    """
    if not token:
        await alert_engine.emit(
            severity=AlertSeverity.WARNING,
            source=AlertSource.AUTH,
            event_type="MISSING_ADMIN_TOKEN",
            message=f"Missing admin token from {request.client.host if request.client else 'unknown'}",
            metadata={"path": request.url.path}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=translate(request, "could_not_validate_credentials")
            or "Authentication required",
        )

    try:
        # Decode token with admin audience validation
        payload = decode_token(token.credentials, TokenAudience.ADMIN)
    except (InvalidTokenError, ValidationError, jwt.InvalidAudienceError) as e:
        await alert_engine.emit(
            severity=AlertSeverity.WARNING,
            source=AlertSource.AUTH,
            event_type="INVALID_ADMIN_TOKEN",
            message=f"Invalid admin token attempt from {request.client.host if request.client else 'unknown'}",
            metadata={"error": str(e), "path": request.url.path}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=translate(request, "could_not_validate_credentials")
            or "Invalid or expired admin token",
        )

    # Extract subject (email) from token
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=translate(request, "invalid_token_payload")
            or "Token missing subject",
        )

    if settings.ADMIN_CACHE_ENABLED:
        cached = await admin_auth_cache.get_profile(email)
        if cached is not None:
            admin_user = _cache_dict_to_admin(cached)
            if not admin_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=translate(request, "inactive_admin_user") or "Admin account is inactive",
                )
            return admin_user

    # Query admin user from database (cache miss)
    statement = select(AdminUser).where(AdminUser.email == email)
    result = await session.execute(statement)
    admin_user = result.scalar_one_or_none()

    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate(request, "admin_user_not_found") or "Admin user not found",
        )

    if not admin_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate(request, "inactive_admin_user") or "Admin account is inactive",
        )

    if settings.ADMIN_CACHE_ENABLED:
        cache_data = _admin_to_cache_dict(admin_user)
        await admin_auth_cache.set_profile(email, cache_data)
        await admin_auth_cache.set_profile(str(admin_user.id), cache_data)

    return admin_user


# Type alias for dependency injection
AdminUserDep = Annotated[AdminUser, Depends(get_current_admin_user)]
