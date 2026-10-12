"""
User Authentication Dependencies
---------------------------------
This module provides FastAPI dependencies for user authentication.

Regular users authenticate separately from admin users and use tokens
with audience="user".

Supports both:
- Authorization: Bearer header (for API clients)
- httpOnly cookie (for browser-based apps using BFF pattern)

Also provides `RecentMfaDep` for step-up authentication on sensitive
operations — validates the X-Step-Up-Token header.
"""

from typing import Annotated, Any
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.core.jwt import decode_token, TokenAudience
from swx_core.auth.core.bearer_or_cookie import BearerOrCookieAuth
from swx_core.auth.auth_cache import user_auth_cache
from swx_core.config.settings import settings
from swx_core.database.db import SessionDep
from swx_core.models.user import User
from swx_core.repositories.user_repository import get_user_by_email
from swx_core.security.refresh_token_service import verify_mfa_token
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


def _get_token_blacklist():
    """Resolve the token blacklist from the DI container, or None if unavailable."""
    try:
        from swx_core.container.container import get_container
        container = get_container()
        if container.bound("auth.token_blacklist"):
            return container.make("auth.token_blacklist")
    except Exception:
        pass
    return None


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

    jti = payload.get("jti")
    if jti:
        blacklist = _get_token_blacklist()
        if blacklist and await blacklist.is_revoked_by_jti(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=translate(request, "token_revoked") or "Token has been revoked",
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
    user = await get_user_by_email(session=session, email=email)

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


class StepUpTokenHeader:
    """Extract and validate the X-Step-Up-Token header for sensitive operations."""

    async def __call__(self, request: Request) -> str:
        token = request.headers.get("X-Step-Up-Token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate(request, "step_up_auth_required") or "Step-up authentication required. Provide X-Step-Up-Token header.",
            )
        result = verify_mfa_token(token)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate(request, "invalid_or_expired_step_up_token") or "Invalid or expired step-up token.",
            )
        email, user_id_str = result
        return user_id_str


_step_up_token_extractor = StepUpTokenHeader()


async def require_recent_mfa(
    user: UserDep,
    request: Request,
    step_up_user_id: Annotated[str, Depends(_step_up_token_extractor)],
) -> User:
    """Dependency that requires recent MFA verification for sensitive operations.

    Validates the X-Step-Up-Token header and ensures it belongs to the
    currently authenticated user. Use this on endpoints that need step-up
    authentication (password change, MFA disable, account deletion, etc.).

    Returns the authenticated User if step-up verification passes.
    Raises HTTP 403 if step-up token is missing, invalid, or doesn't match.
    """
    if str(user.id) != step_up_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate(request, "step_up_token_user_mismatch") or "Step-up token does not match authenticated user.",
        )
    return user


# Dependency alias: requires both UserDep auth AND valid recent MFA step-up
RecentMfaDep = Annotated[User, Depends(require_recent_mfa)]
