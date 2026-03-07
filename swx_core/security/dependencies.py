"""
Authentication & Authorization Dependencies
-------------------------------------------
DEPRECATED: This module is being phased out in favor of domain-specific auth modules.

For new code, use:
- `swx_core.auth.user.dependencies.get_current_user` - For user domain
- `swx_core.auth.admin.dependencies.get_current_admin_user` - For admin domain

This module is kept for backward compatibility during migration.

Legacy Dependencies:
- `get_current_user()`: DEPRECATED - Use swx_core.auth.user.dependencies.get_current_user
- `get_current_active_superuser()`: DEPRECATED - Use admin auth instead
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import select

from swx_core.config.settings import settings
from swx_core.database.db import SessionDep
from swx_core.models.token import TokenPayload
from swx_core.models.user import User
from swx_core.utils.language_helper import translate

# OAuth2 Bearer token authentication setup
reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.ROUTE_PREFIX}/access/auth")
TokenDep = Annotated[str, Depends(reusable_oauth2)]  # Type alias for token dependency


def get_current_user(session: SessionDep, token: TokenDep, request: Request) -> User:  # noqa: F811
    """
    DEPRECATED: Use swx_core.auth.user.dependencies.get_current_user instead.
    
    This function does not validate token audience and is being phased out.
    """
    """
    Retrieves and validates the currently authenticated user based on the provided JWT token.

    Args:
        session (SessionDep): The database session.
        token (TokenDep): The JWT token from the request header.
        request (Request): The HTTP request object.

    Returns:
        User: The authenticated user instance.

    Raises:
        HTTPException (401): If the token is invalid or expired.
        HTTPException (404): If the user is not found in the database.
        HTTPException (400): If the user account is inactive.
    """
    try:
        # Decode JWT token and extract user information
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.PASSWORD_SECURITY_ALGORITHM],
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=translate(request, "could_not_validate_credentials"),
        )

    # Query the user from the database
    statement = select(User).where(User.email == token_data.sub)
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=404, detail=translate(request, "user_not_found")
        )
    if not user.is_active:
        raise HTTPException(
            status_code=400, detail=translate(request, "inactive_user"),
        )

    return user


# Type alias for dependency injection to retrieve the authenticated user
CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser, request: Request) -> User:  # noqa: F811
    """
    DEPRECATED: Use swx_core.auth.admin.dependencies.get_current_admin_user instead.
    
    This function checks is_superuser flag which is being phased out in favor of RBAC.
    
    Ensures that the current authenticated user has superuser privileges.

    Args:
        current_user (CurrentUser): The authenticated user.
        request (Request): The HTTP request object.

    Returns:
        User: The superuser instance.

    Raises:
        HTTPException (403): If the user lacks superuser privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate(request, "insufficient_privileges"),
        )
    return current_user


# Type alias for dependency injection to enforce superuser access
AdminUser = Annotated[User, Depends(get_current_active_superuser)]


# NOTE: require_roles() has been removed.
# This function was broken - it checked for non-existent attributes on the User model.
# Use the proper RBAC system instead:
#   - require_permission() from swx_core.rbac.dependencies
#   - require_role() from swx_core.rbac.dependencies
#   - require_team_permission() from swx_core.rbac.dependencies
#
# Example:
#   from swx_core.rbac.dependencies import require_permission
#   @router.get("/users", dependencies=[Depends(require_permission("user:read"))])
