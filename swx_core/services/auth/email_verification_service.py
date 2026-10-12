# pyright: reportExplicitAny=false, reportAny=false

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.core.jwt import create_token, decode_token, TokenAudience
from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger
from swx_core.models.user import User
from swx_core.repositories.user_repository import get_user_by_email, get_user_by_id
from swx_core.events.dispatcher import event_bus


def generate_email_verification_token(email: str) -> str:
    """Generate a JWT token for email verification.

    Uses a separate secret from access tokens to prevent token confusion.
    Audience is set to 'user' with auth_provider='email-verification'.
    """
    return create_token(
        subject=email,
        audience=TokenAudience.USER,
        expires_delta=timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
        auth_provider="email-verification",
        secret_key=settings.PASSWORD_RESET_SECRET_KEY,
    )


def verify_email_verification_token(token: str) -> str | None:
    """Verify and decode an email verification token.

    Returns the email address if valid, None otherwise.
    """
    try:
        payload = decode_token(
            token,
            TokenAudience.USER,
            secret_key=settings.PASSWORD_RESET_SECRET_KEY,
        )
        if payload.get("auth_provider") != "email-verification":
            return None
        email = payload.get("sub")
        return str(email) if email else None
    except Exception:
        return None


async def auto_verify_if_disabled(session: AsyncSession, user: User) -> None:
    """Auto-set email_verified_at when EMAIL_VERIFICATION_ENABLED is False.

    Called after user registration. Social auth users are always auto-verified
    regardless of this setting since their email is verified by the OAuth provider.
    """
    if not settings.EMAIL_VERIFICATION_ENABLED and user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        session.add(user)
        await session.commit()
        logger.info(f"Email auto-verified (disabled) for user {user.id}")
        await event_bus.dispatch(
            "email.verified",
            payload={"user_id": str(user.id), "email": user.email},
        )


async def mark_social_user_verified(session: AsyncSession, user: User) -> None:
    """Mark a social auth user's email as verified.

    Social login providers (Google, Facebook, etc.) verify email ownership
    during their auth flow, so these users are always email-verified.
    """
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        session.add(user)
        await session.commit()
        logger.info(f"Email auto-verified (social auth) for user {user.id}")
        await event_bus.dispatch(
            "email.verified",
            payload={"user_id": str(user.id), "email": user.email},
        )


async def request_email_verification(
    session: AsyncSession,
    email: str,
    request: Request = None,  # pyright: ignore[reportArgumentType]
) -> str:
    """Generate an email verification token and send the verification email.

    Raises HTTPException 400 if email verification is disabled.
    Raises HTTPException 400 if the email is already verified.
    Raises HTTPException 404 if the user is not found.
    """
    if not settings.EMAIL_VERIFICATION_ENABLED:
        raise HTTPException(status_code=400, detail="Email verification is not enabled")

    user = await get_user_by_email(session=session, email=email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_verified_at is not None:
        raise HTTPException(status_code=400, detail="Email already verified")

    token = generate_email_verification_token(email)

    from swx_core.email.email_service import generate_verify_email, send_email
    email_data = generate_verify_email(email_to=email, token=token)
    send_email(email_to=email, subject=email_data.subject, html_content=email_data.html_content)

    logger.info(f"Email verification requested for {email}")
    await event_bus.dispatch("email.verification_requested", payload={"user_id": str(user.id), "email": email})

    return token


async def verify_email(
    session: AsyncSession,
    token: str,
    request: Request = None,  # pyright: ignore[reportArgumentType]
) -> User:
    """Verify a user's email using the verification token.

    Validates the token, looks up the user, and sets email_verified_at.
    If EMAIL_VERIFICATION_ENABLED is False, returns the user without modification.
    """
    if not settings.EMAIL_VERIFICATION_ENABLED:
        email = verify_email_verification_token(token)
        if email is None:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")
        user = await get_user_by_email(session=session, email=email)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    email = verify_email_verification_token(token)
    if email is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user = await get_user_by_email(session=session, email=email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_verified_at is not None:
        raise HTTPException(status_code=400, detail="Email already verified")

    user.email_verified_at = datetime.now(timezone.utc)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info(f"Email verified for user {user.id}")
    await event_bus.dispatch("email.verified", payload={"user_id": str(user.id), "email": email})

    return user


async def resend_email_verification(
    session: AsyncSession,
    user_id: UUID,
    request: Request = None,  # pyright: ignore[reportArgumentType]
) -> str:
    """Resend email verification for an authenticated user.

    Raises HTTPException 400 if email verification is disabled.
    Raises HTTPException 400 if the email is already verified.
    """
    if not settings.EMAIL_VERIFICATION_ENABLED:
        raise HTTPException(status_code=400, detail="Email verification is not enabled")

    user = await get_user_by_id(session=session, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_verified_at is not None:
        raise HTTPException(status_code=400, detail="Email already verified")

    token = generate_email_verification_token(user.email)

    from swx_core.email.email_service import generate_verify_email, send_email
    email_data = generate_verify_email(email_to=user.email, token=token)
    send_email(email_to=user.email, subject=email_data.subject, html_content=email_data.html_content)

    logger.info(f"Email verification resent for user {user_id}")
    await event_bus.dispatch("email.verification_resent", payload={"user_id": str(user_id), "email": user.email})

    return token