from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.models.referral import ReferralCode, ReferralEvent
from swx_core.repositories import referral_repository


async def get_or_create_code(session: AsyncSession, user_id: UUID) -> ReferralCode:
    code = await referral_repository.get_or_create_referral_code(session, user_id)
    logger.info("Referral code resolved for user %s: %s", user_id, code.code)
    return code


async def apply_referral_code(session: AsyncSession, code: str, referred_user_id: UUID) -> ReferralEvent:
    event = await referral_repository.apply_referral(session, code, referred_user_id)
    await event_bus.dispatch("referral.applied", payload={
        "referral_code": code,
        "referred_user_id": str(referred_user_id),
        "event_id": str(event.id),
    })
    return event


async def list_referrals(session: AsyncSession, user_id: UUID) -> list[ReferralEvent]:
    return await referral_repository.list_referral_events(session, user_id)