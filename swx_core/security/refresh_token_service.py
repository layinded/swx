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
from datetime import timedelta
from typing import Optional

from swx_core.config.settings import settings
from swx_core.models.refresh_token import RefreshToken
from swx_core.repositories import refresh_token_repository as token_repo
from swx_core.security.encryption import encrypt_value, decrypt_value, is_encrypted
from swx_core.utils.language_helper import translate
from swx_core.utils.time import utc_now, ensure_aware


def _encrypt_token(plaintext: str) -> str:
    """Encrypt a refresh token for at-rest storage. No-ops if encryption is not configured."""
    try:
        return encrypt_value(plaintext)
    except Exception:
        return plaintext


def _decrypt_token(ciphertext: str) -> str:
    """Decrypt a stored refresh token. Returns input as-is if not encrypted."""
    if not ciphertext or not is_encrypted(ciphertext):
        return ciphertext
    try:
        return decrypt_value(ciphertext)
    except Exception:
        return ciphertext


async def _audit_logout(session: AsyncSession, email: str, token_id: str) -> None:
    """Record an AUTH_LOGOUT audit event for token revocation."""
    from swx_core.services.audit_logger import AuditLogger, ActorType, AuditOutcome, AuditAction
    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.AUTH_LOGOUT,
        actor_type=ActorType.USER,
        actor_id=email,
        resource_type="session",
        resource_id=token_id,
        outcome=AuditOutcome.SUCCESS,
    )


def create_access_token(
    email: str,
    expires_delta: timedelta,
    auth_provider: str = "local",
    scopes: Optional[list[str]] = None,
    billing_plan: str = "free",
) -> str:
    """
    Generate a short-lived JWT access token for user domain.

    This function creates tokens with audience="user" and optional permission scopes.

    Args:
        email (str): The email of the authenticated user.
        expires_delta (timedelta): The expiration duration of the token.
        auth_provider (str, optional): The authentication provider (default: "local").
        scopes (Optional[list[str]]): Optional list of permission scopes.
        billing_plan (str): Billing plan key embedded in the JWT claim
            (default: "free"). Used by rate-limit middleware.

    Returns:
        str: The encoded JWT access token with audience="user".
    """
    from swx_core.auth.core.jwt import create_token, TokenAudience

    return create_token(
        subject=email,
        audience=TokenAudience.USER,
        expires_delta=expires_delta,
        scopes=scopes,
        auth_provider=auth_provider,
        billing_plan=billing_plan,
    )


def create_mfa_token(email: str, user_id: str, expires_delta: timedelta) -> str:
    """
    Generate a short-lived JWT token for MFA challenge verification.

    This token is issued after successful password authentication when
    MFA is enabled. It authorizes the holder to complete the MFA challenge
    within the expiry window. Audience is "mfa" so it cannot be used as a
    regular access token.

    Args:
        email (str): The email of the authenticated user.
        user_id (str): The UUID of the authenticated user.
        expires_delta (timedelta): Short expiry (default 5 minutes).

    Returns:
        str: The encoded JWT token with audience="mfa".
    """
    from swx_core.auth.core.jwt import create_token, TokenAudience

    return create_token(
        subject=email,
        audience=TokenAudience.MFA,
        expires_delta=expires_delta,
    ) + "." + user_id


def verify_mfa_token(token: str) -> tuple[str, str] | None:
    """
    Decode and validate an MFA challenge token.

    Returns:
        tuple[str, str] | None: (email, user_id) if valid, None otherwise.
    """
    try:
        from swx_core.auth.core.jwt import TokenAudience

        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return None
        jwt_part, user_id = parts
        payload = jwt.decode(
            jwt_part,
            settings.SECRET_KEY,
            algorithms=[settings.PASSWORD_SECURITY_ALGORITHM],
            audience=TokenAudience.MFA.value,
        )
        email = payload.get("sub")
        if not email:
            return None
        return email, user_id
    except Exception:
        return None


async def create_refresh_token(
    session: AsyncSession, email: str, expires_delta: timedelta, auth_provider: str = "local",
    device_info: str | None = None, ip_address: str | None = None,
) -> str:
    expire_at = utc_now() + expires_delta
    encoded_jwt = jwt.encode(
        {"exp": expire_at.timestamp(), "sub": email, "auth_provider": auth_provider},
        settings.REFRESH_SECRET_KEY,
        algorithm=settings.PASSWORD_SECURITY_ALGORITHM,
    )

    from swx_core.services.auth.session_service import enforce_concurrent_limit
    await enforce_concurrent_limit(session, email)

    existing_token = await token_repo.find_token_by_email(session, email)

    if existing_token:
        await token_repo.update_existing_token(
            session, existing_token,
            encrypted_value=_encrypt_token(encoded_jwt),
            expires_at=expire_at,
            last_activity_at=utc_now(),
            device_info=device_info,
            ip_address=ip_address,
        )
    else:
        new_refresh_token = RefreshToken(
            user_email=email, token=_encrypt_token(encoded_jwt), expires_at=expire_at,
            device_info=device_info, ip_address=ip_address, last_activity_at=utc_now(),
        )
        await token_repo.create_token(session, new_refresh_token)

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
            options={"verify_aud": False},
        )
        email = payload.get("sub")
        auth_provider = payload.get("auth_provider", "local")

        if not email:
            raise HTTPException(
                status_code=401,
                detail=translate(request, "invalid_refresh_token_payload"),
            )

        db_token = await token_repo.find_token_by_email(session, email)
        if not db_token or _decrypt_token(db_token.token) != refresh_token:
            raise HTTPException(
                status_code=401,
                detail=translate(request, "invalid_or_revoked_refresh_token"),
            )

        token_exp = ensure_aware(db_token.expires_at)
        if token_exp is not None and utc_now() > token_exp:
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

    Since tokens are encrypted at rest, we decode the JWT to extract the email,
    look up by user_email, then decrypt and compare to find the matching record.

    Args:
        session (AsyncSession): The database session.
        refresh_token (str): The refresh token to revoke.

    Returns:
        bool: True if the token was revoked, False otherwise.
    """
    try:
        payload = jwt.decode(
            refresh_token,
            settings.REFRESH_SECRET_KEY,
            algorithms=[settings.PASSWORD_SECURITY_ALGORITHM],
            options={"verify_aud": False},
        )
        email = payload.get("sub")
    except Exception:
        email = None

    if email:
        all_tokens = await token_repo.find_all_tokens_by_email(session, email)
        for db_token in all_tokens:
            if _decrypt_token(db_token.token) == refresh_token:
                await token_repo.delete_token(session, db_token)
                _audit_logout(session, email, str(db_token.id))
                return True

    # Fallback: match against encrypted storage (only works without at-rest encryption)
    db_token = await token_repo.find_token_by_raw_value(session, refresh_token)
    if db_token:
        await token_repo.delete_token(session, db_token)
        _audit_logout(session, email or "unknown", str(db_token.id))
        return True

    return False


async def revoke_all_tokens(session: AsyncSession, email: str) -> int:
    """Revoke all active refresh tokens for a user (e.g., after a password reset)."""
    from swx_core.repositories import session_repository as session_repo
    from swx_core.services.audit_logger import AuditLogger, ActorType, AuditOutcome, AuditAction

    count = await session_repo.revoke_all_sessions(session, email)
    if count > 0:
        audit = AuditLogger(session)
        await audit.log_event(
            action=AuditAction.AUTH_SESSION_REVOKED,
            actor_type=ActorType.SYSTEM,
            actor_id=email,
            resource_type="session",
            resource_id="all",
            outcome=AuditOutcome.SUCCESS,
            context={"reason": "password_reset", "sessions_revoked": count},
        )
    return count
