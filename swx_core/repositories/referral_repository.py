from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.referral import ReferralCode, ReferralEvent
from swx_core.utils.errors import ConflictError, NotFoundError
from swx_core.utils.time import utc_now


async def get_or_create_referral_code(session: AsyncSession, user_id: UUID) -> ReferralCode:
    stmt = select(ReferralCode).where(ReferralCode.user_id == user_id)  # pyright: ignore[reportArgumentType]
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    import secrets
    code = f"REF-{secrets.token_urlsafe(8).upper()}"
    referral = ReferralCode(user_id=user_id, code=code)
    session.add(referral)
    await session.commit()
    await session.refresh(referral)
    return referral


async def get_referral_code_by_code(session: AsyncSession, code: str) -> ReferralCode | None:
    stmt = select(ReferralCode).where(ReferralCode.code == code)  # pyright: ignore[reportArgumentType]
    return (await session.execute(stmt)).scalar_one_or_none()


async def apply_referral(
    session: AsyncSession, code: str, referred_user_id: UUID
) -> ReferralEvent:
    referral = await get_referral_code_by_code(session, code)
    if referral is None:
        raise NotFoundError("Referral code", code)

    existing = select(ReferralEvent).where(
        ReferralEvent.referral_code_id == referral.id,  # pyright: ignore[reportArgumentType]
        ReferralEvent.referred_user_id == referred_user_id,  # pyright: ignore[reportArgumentType]
    )
    if (await session.execute(existing)).scalar_one_or_none() is not None:
        raise ConflictError("User already referred")

    if referral.referral_count >= referral.max_referrals:
        raise ConflictError("Referral limit reached")
    if referral.expires_at is not None and referral.expires_at < utc_now():
        raise ConflictError("Referral code expired")

    event = ReferralEvent(
        referral_code_id=referral.id,
        referred_user_id=referred_user_id,
    )
    session.add(event)
    referral.referral_count += 1
    session.add(referral)
    await session.commit()
    await session.refresh(event)
    return event


async def list_referral_events(
    session: AsyncSession, user_id: UUID
) -> list[ReferralEvent]:
    code_stmt = select(ReferralCode.id).where(ReferralCode.user_id == user_id)  # pyright: ignore[reportArgumentType]
    code_result = await session.execute(code_stmt)
    code_ids = [row[0] for row in code_result.all()]
    if not code_ids:
        return []
    stmt = select(ReferralEvent).where(ReferralEvent.referral_code_id.in_(code_ids))  # pyright: ignore[reportAttributeAccessIssue]
    return list((await session.execute(stmt)).scalars().all())