"""
Password Security & Token Management
------------------------------------
This module provides:
- **Password hashing & verification** using bcrypt.
- **JWT-based password reset token generation & validation.**
- **Security mechanisms for handling authentication safely.**

Key Functions:
- `verify_password()`: Check if a plaintext password matches a hashed password.
- `get_password_hash()`: Hash a password securely.
- `generate_password_reset_token()`: Create a JWT token for password reset.
- `verify_password_reset_token()`: Validate and decode a password reset token.

"""

import asyncio
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.auth.core.jwt import create_token, decode_token, TokenAudience

# Password hashing context (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a securely hashed password.
    Runs the blocking verify operation in a threadpool to avoid blocking the event loop.

    Args:
        plain_password (str): The user-provided plaintext password.
        hashed_password (str): The stored bcrypt-hashed password.

    Returns:
        bool: True if the password is valid, False otherwise.
    """
    return await asyncio.to_thread(pwd_context.verify, plain_password, hashed_password)


async def get_password_hash(password: str) -> str:
    """
    Hash a password securely using bcrypt.
    Runs the blocking hash operation in a threadpool to avoid blocking the event loop.

    Args:
        password (str): The plaintext password.

    Returns:
        str: The hashed password.
    """
    return await asyncio.to_thread(pwd_context.hash, password)


async def generate_password_reset_token(
    session: AsyncSession,
    email: str,
    auth_provider: str = "local",
) -> str | None:
    """
    Generate a JWT token for password reset.

    This function uses a separate secret key and explicit audience to prevent
    token type confusion with access tokens.

    This function is only available for users with `auth_provider = local` (i.e., not social login users).

    Args:
        session: Database session for settings access
        email (str): The email address associated with the user.
        auth_provider (str, optional): The authentication provider. Defaults to `"local"`.

    Returns:
        str | None: A JWT reset token, or None if the user uses a social login provider.
    """
    if auth_provider != "local":
        return None  # Social login users should reset passwords via their provider.

    # Set token expiration time from settings (DB -> .env -> default)
    from swx_core.services.settings_helper import get_token_expiration
    expires_delta = await get_token_expiration(session, "password_reset")

    # Create token with explicit audience and separate secret key
    # Note: Using "user" audience but with separate secret to prevent confusion
    return create_token(
        subject=email,
        audience=TokenAudience.USER,  # Password reset is for user domain
        expires_delta=expires_delta,
        auth_provider="local",
        secret_key=settings.PASSWORD_RESET_SECRET_KEY,  # Separate secret for reset tokens
    )


def verify_password_reset_token(token: str) -> str | None:
    """
    Verify and decode a password reset token.

    This function validates the token using the separate password reset secret key
    and ensures it has the correct audience.

    Args:
        token (str): The JWT reset token.

    Returns:
        str | None: The email associated with the reset token if valid, otherwise None.
    """
    try:
        # Decode token using separate secret key and validate audience
        decoded_token = decode_token(
            token,
            TokenAudience.USER,
            secret_key=settings.PASSWORD_RESET_SECRET_KEY,
        )

        # Return the email stored in the token
        return str(decoded_token["sub"])

    except (ExpiredSignatureError, InvalidTokenError, jwt.InvalidAudienceError):
        return None  # Invalid or expired token
