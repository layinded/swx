"""
Billing Plan Helper
-------------------
Resolves a user's active billing plan key for JWT embedding
and rate-limit-aware middleware.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger
from swx_core.repositories.billing_repository import (  # pyright: ignore[reportMissingImports]
    get_user_billing_account,
    get_active_subscription,
    get_plan_by_id,
    is_subscription_expired,
)


async def get_user_plan_key(session: AsyncSession, user_id: UUID) -> str:
    """Resolve the active billing plan key for *user_id*.

    Queries ``BillingAccount -> Subscription -> Plan`` via the repository
    layer and returns the plan ``key`` (e.g. ``"free"``, ``"pro"``).
    Falls back to ``settings.DEFAULT_PLAN_KEY`` when no active subscription or on any error.
    """
    try:
        account = await get_user_billing_account(session, user_id)
        if not account:
            return settings.DEFAULT_PLAN_KEY

        subscription = await get_active_subscription(session, account.id)
        if not subscription or is_subscription_expired(subscription):
            return settings.DEFAULT_PLAN_KEY

        plan = await get_plan_by_id(session, subscription.plan_id)
        return plan.key if plan else settings.DEFAULT_PLAN_KEY
    except Exception as e:
        logger.warning(f"Failed to resolve billing plan for {user_id}: {e}")
        return settings.DEFAULT_PLAN_KEY
