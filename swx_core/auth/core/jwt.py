"""
JWT Token Utilities
-------------------
This module provides core JWT token creation and validation utilities.

Supports different token audiences for different domains:
- "admin": Admin domain tokens
- "user": User domain tokens
- "system": System domain tokens
"""

import jwt
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Dict, Any

from swx_core.config.settings import settings


class TokenAudience(str, Enum):
    """Token audience types for different domains."""

    ADMIN = "admin"
    USER = "user"
    SYSTEM = "system"


def create_token(
    subject: str,
    audience: TokenAudience,
    expires_delta: timedelta,
    scopes: Optional[list[str]] = None,
    auth_provider: str = "local",
    secret_key: Optional[str] = None,
) -> str:
    """
    Create a JWT token with explicit audience and scopes.

    Args:
        subject: The token subject (usually email or user ID).
        audience: The token audience (admin, user, or system).
        expires_delta: Token expiration duration.
        scopes: Optional list of permission scopes.
        auth_provider: Authentication provider (default: "local").
        secret_key: Optional secret key (defaults to settings.SECRET_KEY).

    Returns:
        Encoded JWT token string.
    """
    if secret_key is None:
        secret_key = settings.SECRET_KEY

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode: Dict[str, Any] = {
        "exp": expire.timestamp(),
        "sub": subject,
        "aud": audience.value,
        "auth_provider": auth_provider,
    }

    if scopes:
        to_encode["scope"] = " ".join(scopes)

    return jwt.encode(
        to_encode,
        secret_key,
        algorithm=settings.PASSWORD_SECURITY_ALGORITHM,
    )


def decode_token(
    token: str,
    audience: TokenAudience,
    secret_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token to decode.
        audience: Expected token audience.
        secret_key: Optional secret key (defaults to settings.SECRET_KEY).

    Returns:
        Decoded token payload.

    Raises:
        jwt.InvalidTokenError: If token is invalid, expired, or audience mismatch.
    """
    if secret_key is None:
        secret_key = settings.SECRET_KEY

    payload = jwt.decode(
        token,
        secret_key,
        algorithms=[settings.PASSWORD_SECURITY_ALGORITHM],
        audience=audience.value,
    )

    # Validate audience matches
    if payload.get("aud") != audience.value:
        raise jwt.InvalidTokenError(f"Token audience mismatch: expected {audience.value}")

    return payload


def get_token_scopes(payload: Dict[str, Any]) -> list[str]:
    """
    Extract scopes from token payload.

    Args:
        payload: Decoded JWT payload.

    Returns:
        List of permission scopes.
    """
    scope_str = payload.get("scope", "")
    if not scope_str:
        return []
    return scope_str.split()
