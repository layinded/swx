from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.models.billing import BillingAccount, BillingAccountType, Plan
from swx_core.models.credit_pack import CreditPack
from swx_core.repositories import billing_repository


async def get_plan_by_key(session: AsyncSession, plan_key: str) -> Plan | None:
    return await billing_repository.get_plan_by_key(session, plan_key)


async def list_public_plans(session: AsyncSession) -> list[Plan]:
    return await billing_repository.list_public_plans(session)


async def get_credit_pack_by_key(session: AsyncSession, pack_key: str) -> CreditPack | None:
    return await billing_repository.get_credit_pack_by_key(session, pack_key)


async def list_public_credit_packs(session: AsyncSession) -> list[CreditPack]:
    return await billing_repository.list_public_credit_packs(session)


async def get_user_billing_account(session: AsyncSession, user_id: UUID) -> BillingAccount | None:
    return await billing_repository.get_user_billing_account(session, user_id)


async def get_plan_monthly_quota(session: AsyncSession, user_id: UUID, feature_key: str = "ai.tokens_per_month") -> int:
    """Resolve the user's monthly token quota from their plan entitlement.

    Falls back to ``settings.QUOTA_MONTHLY_DEFAULT_TOKENS`` if the user has
    no billing account, no active subscription, or no entitlement for the
    given feature key.
    """
    from swx_core.services.billing.entitlement_resolver import EntitlementResolver

    resolver = EntitlementResolver(session)
    entitlement = await resolver.get_entitlement(user_id, BillingAccountType.USER, feature_key)

    if entitlement is None:
        return settings.QUOTA_MONTHLY_DEFAULT_TOKENS

    try:
        limit = int(entitlement)
    except ValueError:
        return settings.QUOTA_MONTHLY_DEFAULT_TOKENS

    if limit == -1:
        return settings.QUOTA_MONTHLY_DEFAULT_TOKENS

    return limit
