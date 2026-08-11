"""
Plan Resolver
-------------
Resolves the effective plan tier for a user or team, accounting for trial periods.

Trial-aware resolution:
- If the subscription has ``trial_ends_at`` set and it is in the future, the
  ``TRIAL_PLAN_KEY`` tier is returned (default: "enterprise").
- Otherwise the actual plan key is classified as "enterprise", "pro", or "free".
- If no active subscription exists, returns "free".
"""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_

from swx_core.config.settings import settings
from swx_core.models.billing import (
    BillingAccount,
    BillingAccountType,
    Plan,
    Subscription,
)
from swx_core.utils.time import utc_now


class PlanResolver:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _find_subscription(
        self,
        owner_id: uuid.UUID,
        account_type: BillingAccountType,
    ) -> Optional[Subscription]:
        stmt = (
            select(Subscription)
            .join(BillingAccount, Subscription.account_id == BillingAccount.id)
            .where(
                and_(
                    BillingAccount.owner_id == owner_id,
                    BillingAccount.account_type == account_type,
                    Subscription.current_period_end >= utc_now(),
                )
            )
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_plan_tier(
        self,
        team_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> str:
        """Return the effective plan tier: "enterprise", "pro", or "free".

        Resolution order:
        1. If *team_id* is provided, look up the TEAM subscription first.
        2. Fall back to the USER subscription if *user_id* is provided.
        3. If an active trial is found, return ``TRIAL_PLAN_KEY``.
        4. Otherwise classify the plan key.
        """
        subscription: Optional[Subscription] = None

        if team_id:
            subscription = await self._find_subscription(team_id, BillingAccountType.TEAM)

        if not subscription and user_id:
            subscription = await self._find_subscription(user_id, BillingAccountType.USER)

        if not subscription:
            return "free"

        if subscription.trial_ends_at and subscription.trial_ends_at > utc_now():
            return settings.TRIAL_PLAN_KEY

        plan = await self.session.get(Plan, subscription.plan_id)
        if not plan:
            return "free"

        plan_key = (plan.key or "").lower()

        if "enterprise" in plan_key:
            return "enterprise"
        if "pro" in plan_key:
            return "pro"
        return "free"


def get_plan_resolver(session: AsyncSession) -> PlanResolver:
    return PlanResolver(session)