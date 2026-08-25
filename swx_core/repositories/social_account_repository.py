from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.social_account import SocialAccount
from swx_core.models.user import User


async def get_linked_accounts(session: AsyncSession, user_id: UUID) -> list[SocialAccount]:
    stmt = select(SocialAccount).where(SocialAccount.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_account_by_provider(
    session: AsyncSession, provider: str, provider_id: str
) -> SocialAccount | None:
    stmt = select(SocialAccount).where(
        SocialAccount.provider == provider,
        SocialAccount.provider_id == provider_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_by_provider(
    session: AsyncSession, provider: str, provider_id: str
) -> User | None:
    social_account = await get_account_by_provider(session, provider, provider_id)
    if social_account is None:
        return None
    stmt = select(User).where(User.id == social_account.user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def link_account(
    session: AsyncSession,
    user_id: UUID,
    provider: str,
    provider_id: str,
    provider_email: str | None = None,
    display_name: str | None = None,
    avatar_url: str | None = None,
) -> SocialAccount:
    account = SocialAccount(
        user_id=user_id,
        provider=provider,
        provider_id=provider_id,
        provider_email=provider_email,
        display_name=display_name,
        avatar_url=avatar_url,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def unlink_account(session: AsyncSession, user_id: UUID, provider: str) -> bool:
    stmt = select(SocialAccount).where(
        SocialAccount.user_id == user_id,
        SocialAccount.provider == provider,
    )
    account = (await session.execute(stmt)).scalar_one_or_none()
    if account is None:
        return False
    await session.delete(account)
    await session.commit()
    return True


async def has_provider_linked(session: AsyncSession, user_id: UUID, provider: str) -> bool:
    stmt = select(SocialAccount).where(
        SocialAccount.user_id == user_id,
        SocialAccount.provider == provider,
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def has_local_password(session: AsyncSession, user_id: UUID) -> bool:
    stmt = select(User).where(User.id == user_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    return user is not None and user.hashed_password is not None