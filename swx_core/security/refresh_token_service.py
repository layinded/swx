"""
Refresh Token & Authentication Token Management
----------------------------------------------
This module provides:
- **Access token generation** for authentication (user domain).
- **Refresh token generation, validation, and revocation**.
- **Token-based authentication using JWT (JSON Web Tokens).**
- **Secure storage & management of refresh tokens in the database.**

Key Functions:
- `create_access_token()`: Generates a short-lived access token with audience="user".
- `create_refresh_token()`: Creates a refresh token stored in the database.
- `verify_refresh_token()`: Validates refresh tokens before issuing new access tokens.
- `revoke_refresh_token()`: Logs out a user by invalidating a refresh token.
- `revoke_all_tokens()`: Revokes all active refresh tokens (e.g., after password reset).

NOTE: This module is for USER domain tokens. Admin tokens should use admin auth module.
"""

import jwt
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete
from datetime import datetime, timedelta, timezone
from typing import Optional

from swx_core.config.settings import settings
from swx_core.models.refresh_token import RefreshToken
from swx_core.auth.core.jwt import create_token, TokenAudience
from swx_core.utils.language_helper import translate


def create_access_token(
    email: str,
    expires_delta: timedelta,
    auth_provider: str = "local",
    scopes: Optional[list[str]] = None,
) -> str:
    """
    Generate a short-lived JWT access token for user domain.

    This function creates tokens with audience="user" and optional permission scopes.

    Args:
        email (str): The email of the authenticated user.
        expires_delta (timedelta): The expiration duration of the token.
        auth_provider (str, optional): The authentication provider (default: "local").
        scopes (Optional[list[str]]): Optional list of permission scopes.

    Returns:
        str: The encoded JWT access token with audience="user".
    """
    return create_token(
        subject=email,
        audience=TokenAudience.USER,
        expires_delta=expires_delta,
        scopes=scopes,
        auth_provider=auth_provider,
    )


async def create_refresh_token(
    session: AsyncSession, email: str, expires_delta: timedelta, auth_provider: str = "local"
) -> str:
    """
    Create or update a refresh token for the user.

    - If a refresh token exists, update it instead of creating a new one.
    - If no token exists, create a new refresh token.

    Args:
        session (AsyncSession): The database session.
        email (str): The email of the user.
        expires_delta (timedelta): The expiration duration of the refresh token.
        auth_provider (str, optional): The authentication provider (default: "local").

    Returns:
        str: The encoded JWT refresh token.
    """
    expire_at = datetime.now(timezone.utc) + expires_delta
    # Convert to timezone-naive for database storage
    expire_at_naive = expire_at.replace(tzinfo=None)
    encoded_jwt = jwt.encode(
        {"exp": expire_at.timestamp(), "sub": email, "auth_provider": auth_provider},
        settings.REFRESH_SECRET_KEY,
        algorithm=settings.PASSWORD_SECURITY_ALGORITHM,
    )

    # Check if a refresh token already exists for this user
    statement = select(RefreshToken).where(RefreshToken.user_email == email)
    result = await session.execute(statement)
    existing_token = result.scalar_one_or_none()

    if existing_token:
        # Update the existing refresh token
        existing_token.token = encoded_jwt
        existing_token.expires_at = expire_at_naive
    else:
        # Create a new refresh token record
        new_refresh_token = RefreshToken(
            user_email=email, token=encoded_jwt, expires_at=expire_at_naive
        )
        session.add(new_refresh_token)

    await session.commit()
    return encoded_jwt


async def verify_refresh_token(
    session: AsyncSession, refresh_token: str, request: Request
) -> tuple[str, str] | None:
    """
    Verify the refresh token and return (email, auth_provider) if valid.

    - Checks if the token exists in the database and is not expired.
    - Returns user email and authentication provider.

    Args:
        session (AsyncSession): The database session.
        refresh_token (str): The refresh token to verify.
        request (Request): The FastAPI request object for localization.

    Returns:
        tuple[str, str] | None: The email and auth provider if valid, otherwise None.

    Raises:
        HTTPException: If the token is invalid, revoked, or expired.
    """
    try:
        # Decode the JWT refresh token using the REFRESH_SECRET_KEY
        payload = jwt.decode(
            refresh_token,
            settings.REFRESH_SECRET_KEY,
            algorithms=[settings.PASSWORD_SECURITY_ALGORITHM],
        )
        email = payload.get("sub")
        auth_provider = payload.get("auth_provider", "local")

        if not email:
            raise HTTPException(
                status_code=401,
                detail=translate(request, "invalid_refresh_token_payload"),
            )

        # Validate that the token exists in the database
        statement = select(RefreshToken).where(RefreshToken.token == refresh_token)
        result = await session.execute(statement)
        db_token = result.scalar_one_or_none()
        if not db_token:
            raise HTTPException(
                status_code=401,
                detail=translate(request, "invalid_or_revoked_refresh_token"),
            )

        # Ensure token expiration is timezone-aware (assume UTC if naive)
        token_exp = db_token.expires_at
        if token_exp.tzinfo is None:
            token_exp = token_exp.replace(tzinfo=timezone.utc)

        # Check if the token is expired
        if datetime.now(timezone.utc) > token_exp:
            raise HTTPException(
                status_code=401, detail=translate(request, "refresh_token_expired")
            )

        return email, auth_provider
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail=translate(request, "refresh_token_expired")
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401, detail=translate(request, "invalid_refresh_token")
        )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail=translate(request, "invalid_or_revoked_refresh_token"),
        )


async def revoke_refresh_token(session: AsyncSession, refresh_token: str) -> bool:
    """
    Revoke a refresh token (logout).

    Args:
        session (AsyncSession): The database session.
        refresh_token (str): The refresh token to revoke.

    Returns:
        bool: True if the token was revoked, False otherwise.
    """
    statement = select(RefreshToken).where(RefreshToken.token == refresh_token)
    result = await session.execute(statement)
    db_token = result.scalar_one_or_none()
    if db_token:
        await session.delete(db_token)
        await session.commit()

    # Return True regardless to indicate that the token is no longer valid
    return True


async def revoke_all_tokens(session: AsyncSession, email: str) -> None:
    """
    Revoke all active refresh tokens for a user (e.g., after a password reset).

    Args:
        session (AsyncSession): The database session.
        email (str): The email of the user whose tokens should be revoked.
    """
    statement = delete(RefreshToken).where(RefreshToken.user_email == email)
    await session.execute(statement)
    await session.commit()
