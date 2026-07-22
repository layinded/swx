"""
User Authentication Dependencies
---------------------------------
This module provides FastAPI dependencies for user authentication.

Regular users authenticate separately from admin users and use tokens
with audience="user".

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
from swx_core.auth.auth_cache import user_auth_cache
from swx_core.config.settings import settings
from swx_core.database.db import SessionDep
from swx_core.models.user import User
from swx_core.utils.language_helper import translate
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType
from swx_core.core.tenant import set_current_tenant, set_super_admin

# Bearer or Cookie authentication for user endpoints (BFF pattern)
user_auth = BearerOrCookieAuth()
UserTokenDep = Annotated[HTTPAuthorizationCredentials | None, Depends(user_auth)]

_USER_CACHE_FIELDS = (
    "id", "email", "full_name", "is_active", "is_superuser",
    "auth_provider", "provider_id", "avatar_url", "preferred_language",
    "tenant_id", "created_at", "updated_at",
)


def _user_to_cache_dict(user: User) -> dict[str, Any]:
    return {field: getattr(user, field) for field in _USER_CACHE_FIELDS}


def _cache_dict_to_user(data: dict[str, Any]) -> User:
    return User(**data)


async def get_current_user(
    session: SessionDep,
    token: UserTokenDep,
    request: Request,
) -> User:
    """Retrieves and validates the currently authenticated user.

    This function:
    1. Validates the JWT token with audience="user"
    2. Checks token scopes (if any)
    3. Retrieves the user from L1/L2 cache or database
    4. Validates the user is active

    Supports token from:
    - Authorization: Bearer header (API clients)
    - httpOnly cookie (browser-based apps)

    Args:
        session: Database session (AsyncSession).
        token: JWT token from request header or cookie.
        request: HTTP request object.

    Returns:
        User: The authenticated user.

    Raises:
        HTTPException (401): If token is invalid, expired, or wrong audience.
        HTTPException (404): If user not found.
        HTTPException (400): If user account is inactive.
    """
    if not token:
        await alert_engine.emit(
            severity=AlertSeverity.INFO,
            source=AlertSource.AUTH,
            event_type="MISSING_USER_TOKEN",
            message=f"Missing user token from {request.client.host if request.client else 'unknown'}",
            metadata={"path": request.url.path}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=translate(request, "could_not_validate_credentials")
            or "Authentication required",
        )

    try:
        # Decode token with user audience validation
        payload = decode_token(token.credentials, TokenAudience.USER)
    except (InvalidTokenError, ValidationError, jwt.InvalidAudienceError) as e:
        await alert_engine.emit(
            severity=AlertSeverity.INFO,
            source=AlertSource.AUTH,
            event_type="INVALID_USER_TOKEN",
            message=f"Invalid user token attempt from {request.client.host if request.client else 'unknown'}",
            metadata={"error": str(e), "path": request.url.path}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=translate(request, "could_not_validate_credentials")
            or "Invalid or expired user token",
        )

    # Extract subject (email) from token
    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=translate(request, "invalid_token_payload")
            or "Token missing subject",
        )

    if settings.USER_CACHE_ENABLED:
        cached = await user_auth_cache.get_profile(email)
        if cached is not None:
            user = _cache_dict_to_user(cached)
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=translate(request, "inactive_user") or "User account is inactive",
                )
            if user.tenant_id:
                set_current_tenant(user.tenant_id)
            if user.is_superuser:
                set_super_admin(True)
            return user

    # Query user from database (cache miss)
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate(request, "user_not_found") or "User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate(request, "inactive_user") or "User account is inactive",
        )

    if settings.USER_CACHE_ENABLED:
        cache_data = _user_to_cache_dict(user)
        await user_auth_cache.set_profile(email, cache_data)
        await user_auth_cache.set_profile(str(user.id), cache_data)

    if user.tenant_id:
        set_current_tenant(user.tenant_id)

    if user.is_superuser:
        set_super_admin(True)

    return user

# Type alias for dependency injection
UserDep = Annotated[User, Depends(get_current_user)]
