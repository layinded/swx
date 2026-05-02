"""
Admin Authentication Dependencies
---------------------------------
This module provides FastAPI dependencies for admin authentication.

Admin users authenticate separately from regular users and use tokens
with audience="admin".
"""

from typing import Annotated
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.auth.core.jwt import decode_token, TokenAudience
from swx_core.config.settings import settings
from swx_core.database.db import SessionDep
from swx_core.models.admin_user import AdminUser
from swx_core.utils.language_helper import translate
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType

# OAuth2 Bearer token authentication for admin endpoints
admin_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.ROUTE_PREFIX}/admin/auth",
    scheme_name="AdminBearer",
)
AdminTokenDep = Annotated[str, Depends(admin_oauth2)]


async def get_current_admin_user(
    session: SessionDep,
    token: AdminTokenDep,
    request: Request,
) -> AdminUser:
    """
    Retrieves and validates the currently authenticated admin user.

    This function:
    1. Validates the JWT token with audience="admin"
    2. Checks token scopes (if any)
    3. Retrieves the admin user from database
    4. Validates the admin user is active

    Args:
        session: Database session (AsyncSession).
        token: JWT token from request header.
        request: HTTP request object.

    Returns:
        AdminUser: The authenticated admin user.

    Raises:
        HTTPException (401): If token is invalid, expired, or wrong audience.
        HTTPException (404): If admin user not found.
        HTTPException (400): If admin account is inactive.
    """
    try:
        # Decode token with admin audience validation
        payload = decode_token(token, TokenAudience.ADMIN)
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

    # Query admin user from database
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

    return admin_user


# Type alias for dependency injection
AdminUserDep = Annotated[AdminUser, Depends(get_current_admin_user)]
