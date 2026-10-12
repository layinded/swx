from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.services.billing import referral_service


async def get_referral_code_controller(session: AsyncSession, user_id: UUID) -> dict[str, object]:
    code = await referral_service.get_or_create_code(session, user_id)
    return {
        "code": code.code,
        "referral_count": code.referral_count,
        "max_referrals": code.max_referrals,
        "bonus_tokens": code.bonus_tokens,
        "is_active": code.is_active,
    }


async def list_referrals_controller(session: AsyncSession, user_id: UUID) -> list[dict[str, object]]:
    events = await referral_service.list_referrals(session, user_id)
    return [
        {
            "id": str(event.id),
            "referred_user_id": str(event.referred_user_id),
            "referrer_bonus_credited": event.referrer_bonus_credited,
            "referred_bonus_credited": event.referred_bonus_credited,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]