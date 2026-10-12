# pyright: reportExplicitAny=false, reportAny=false

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger
from swx_core.models.social_account import SocialAccount, SocialAccountPublic
from swx_core.models.user import User
from swx_core.repositories import social_account_repository
from swx_core.repositories.user_repository import get_user_by_email
from swx_core.events.dispatcher import event_bus


async def link_social_account(
    session: AsyncSession,
    user_id: UUID,
    provider: str,
    provider_id: str,
    provider_email: str | None = None,
    display_name: str | None = None,
    avatar_url: str | None = None,
) -> SocialAccountPublic:
    """Link a social provider to an existing user account.

    Prevents linking a provider that's already linked to another user.
    Requires email verification for local-auth users when EMAIL_VERIFICATION_ENABLED.
    """
    existing = await social_account_repository.get_account_by_provider(session, provider, provider_id)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Provider '{provider}' is already linked to another account",
        )

    already_linked = await social_account_repository.has_provider_linked(session, user_id, provider)
    if already_linked:
        raise HTTPException(
            status_code=409,
            detail=f"Provider '{provider}' is already linked to your account",
        )

    account = await social_account_repository.link_account(
        session=session,
        user_id=user_id,
        provider=provider,
        provider_id=provider_id,
        provider_email=provider_email,
        display_name=display_name,
        avatar_url=avatar_url,
    )

    logger.info(f"Linked {provider} account to user {user_id}")
    await event_bus.dispatch("account.linked", payload={
        "user_id": str(user_id),
        "provider": provider,
        "provider_id": provider_id,
    })

    return SocialAccountPublic.model_validate(account)


async def unlink_social_account(
    session: AsyncSession,
    user_id: UUID,
    provider: str,
) -> dict[str, bool]:
    """Unlink a social provider from a user account.

    Prevents unlinking if the user has no local password and this is their
    only authentication method (would lock them out).
    """
    has_password = await social_account_repository.has_local_password(session, user_id)
    linked_accounts = await social_account_repository.get_linked_accounts(session, user_id)

    if not has_password and len(linked_accounts) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot unlink the only authentication method. Set a password first.",
        )

    removed = await social_account_repository.unlink_account(session, user_id, provider)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' is not linked to your account")

    logger.info(f"Unlinked {provider} account from user {user_id}")
    await event_bus.dispatch("account.unlinked", payload={
        "user_id": str(user_id),
        "provider": provider,
    })

    return {"unlinked": True}


async def get_linked_accounts(session: AsyncSession, user_id: UUID) -> list[SocialAccountPublic]:
    """Get all social accounts linked to a user."""
    accounts = await social_account_repository.get_linked_accounts(session, user_id)
    return [SocialAccountPublic.model_validate(a) for a in accounts]


async def find_or_create_user_from_social(
    session: AsyncSession,
    email: str,
    provider: str,
    provider_id: str,
    display_name: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Find an existing user by social account or email, or create a new one.

    Account linking flow:
    1. Check if a SocialAccount exists for this provider+provider_id -> return that user
    2. Check if a User exists with this email:
       a. If yes and email is verified -> link the social account to that user
       b. If yes and email is NOT verified -> reject (potential account takeover)
    3. If no user found -> create a new user with auth_provider=provider

    Social auth users are always auto-verified since the provider confirms email.
    """
    existing_account = await social_account_repository.get_account_by_provider(session, provider, provider_id)
    if existing_account is not None:
        from swx_core.repositories.user_repository import get_user_by_id
        user = await get_user_by_id(session, existing_account.user_id)
        if user is None:
            raise HTTPException(status_code=500, detail="Linked user not found")
        return user

    existing_user = await get_user_by_email(session=session, email=email)

    if existing_user is not None:
        if settings.EMAIL_VERIFICATION_ENABLED and existing_user.email_verified_at is None:
            raise HTTPException(
                status_code=409,
                detail="An account with this email exists but is not verified. "
                       "Verify your email first, then link your social account.",
            )

        await social_account_repository.link_account(
            session=session,
            user_id=existing_user.id,
            provider=provider,
            provider_id=provider_id,
            provider_email=email,
            display_name=display_name,
            avatar_url=avatar_url,
        )

        logger.info(f"Linked {provider} account to existing user {existing_user.id}")
        await event_bus.dispatch("account.linked", payload={
            "user_id": str(existing_user.id),
            "provider": provider,
            "provider_id": provider_id,
        })

        from swx_core.services.auth.email_verification_service import mark_social_user_verified
        await mark_social_user_verified(session, existing_user)
        return existing_user

    new_user = User(
        email=email,
        full_name=display_name or email.split("@")[0],
        auth_provider=provider,
        provider_id=provider_id,
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    await social_account_repository.link_account(
        session=session,
        user_id=new_user.id,
        provider=provider,
        provider_id=provider_id,
        provider_email=email,
        display_name=display_name,
        avatar_url=avatar_url,
    )

    logger.info(f"Created new user {new_user.id} via {provider} and linked account")
    await event_bus.dispatch("user.created", payload={
        "id": str(new_user.id),
        "data": {
            "email": email,
            "full_name": new_user.full_name,
            "auth_provider": provider,
        },
    })
    await event_bus.dispatch("account.linked", payload={
        "user_id": str(new_user.id),
        "provider": provider,
        "provider_id": provider_id,
    })

    return new_user