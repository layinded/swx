"""
User Authentication Dependencies
---------------------------------
This module provides FastAPI dependencies for user authentication.

Regular users authenticate separately from admin users and use tokens
with audience="user".
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
from swx_core.models.user import User
from swx_core.utils.language_helper import translate
from swx_core.services.alert_engine import alert_engine
from swx_core.services.channels.models import AlertSeverity, AlertSource, AlertActorType

# OAuth2 Bearer token authentication for user endpoints
user_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.ROUTE_PREFIX}/access/auth",
    scheme_name="UserBearer",
)
UserTokenDep = Annotated[str, Depends(user_oauth2)]


async def get_current_user(
    session: SessionDep,
    token: UserTokenDep,
    request: Request,
) -> User:
    """
    Retrieves and validates the currently authenticated user.

    This function:
    1. Validates the JWT token with audience="user"
    2. Checks token scopes (if any)
    3. Retrieves the user from database
    4. Validates the user is active

    Args:
        session: Database session (AsyncSession).
        token: JWT token from request header.
        request: HTTP request object.

    Returns:
        User: The authenticated user.

    Raises:
        HTTPException (401): If token is invalid, expired, or wrong audience.
        HTTPException (404): If user not found.
        HTTPException (400): If admin account is inactive.
    """
    try:
        # Decode token with user audience validation
        payload = decode_token(token, TokenAudience.USER)
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

    # Query user from database
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

    return user


# Type alias for dependency injection
UserDep = Annotated[User, Depends(get_current_user)]
