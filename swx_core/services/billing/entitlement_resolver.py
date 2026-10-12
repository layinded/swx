"""
Entitlement Resolver
--------------------
Central service for resolving entitlements for actors (Users or Teams).
"""

import uuid
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select, and_

from swx_core.utils.time import utc_now

from swx_core.config.settings import settings
from swx_core.models.billing import (
    BillingAccount,
    BillingAccountType,
    Plan,
    Subscription,
    SubscriptionStatus,
    PlanEntitlement,
    Feature,
    UsageRecord,
)
from swx_core.services.billing.feature_registry import FeatureRegistry, FeatureType
from swx_core.middleware.logging_middleware import logger

# Subscriptions in these statuses grant access (PAST_DUE = grace period, TRIALING = trial)
_ACTIVE_STATUSES = frozenset({SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE, SubscriptionStatus.TRIALING})

# Sentinel for unlimited quota (plan value of -1)
UNLIMITED_QUOTA = 999_999_999


class EntitlementResolver:
    """
    Resolves if an actor has access to a feature.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_account_and_subscription(
        self,
        owner_id: uuid.UUID,
        account_type: BillingAccountType,
    ) -> Tuple[Optional[BillingAccount], Optional[Subscription]]:
        """Look up billing account and active subscription. Returns (account, subscription).
        
        When a subscription has trial_ends_at set and the trial has not expired,
        the subscription is considered active regardless of its status field.
        This bridges the gap for newly registered users whose TEAM subscription
        carries trial entitlements before they convert to a paid plan.
        """
        stmt = select(BillingAccount).where(
            and_(
                BillingAccount.owner_id == owner_id,
                BillingAccount.account_type == account_type,
            )
        )
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            return None, None

        now = utc_now()
        stmt = select(Subscription).where(
            and_(
                Subscription.account_id == account.id,
                Subscription.current_period_end >= now,
            )
        ).where(
            # Active status OR unexpired trial
            (  # pyright: ignore[reportOperatorIssue]
                Subscription.status.in_(_ACTIVE_STATUSES)  # pyright: ignore[reportAttributeAccessIssue]
            ) | (
                Subscription.trial_ends_at != None  # noqa: E711  # pyright: ignore[reportUnusedExpression]
            ) & (
                Subscription.trial_ends_at > now  # pyright: ignore[reportUnusedExpression]
            )
        )
        result = await self.session.execute(stmt)
        subscription = result.scalar_one_or_none()
        return account, subscription

    async def has(
        self,
        owner_id: uuid.UUID,
        account_type: BillingAccountType,
        feature_key: str,
    ) -> bool:
        """
        Check if an account has access to a feature.
        """
        # Check registry first (in-memory, no DB cost)
        feature_def = FeatureRegistry.get(feature_key)
        if not feature_def:
            logger.warning("Feature key '%s' not found in registry.", feature_key)
            return False

        if feature_def.feature_type == FeatureType.BOOLEAN:
            entitlement = await self.get_entitlement(owner_id, account_type, feature_key)
            return entitlement is not None and entitlement.lower() == "true"

        if feature_def.feature_type == FeatureType.QUOTA:
            # For quota, 'has' means 'has any remaining quota'
            remaining = await self.get_remaining_quota(owner_id, account_type, feature_key)
            return remaining > 0

        return False

    async def _resolve_effective_plan_id(
        self,
        subscription: Subscription,
    ) -> uuid.UUID:
        """Return the plan ID that governs entitlements for this subscription.

        During an active trial, the trial plan's entitlements apply instead of
        the subscription's base plan.  This is what makes a "free" plan user
        receive "enterprise" entitlements for the trial period.
        """
        if subscription.trial_ends_at and subscription.trial_ends_at > utc_now():
            trial_plan_key = settings.TRIAL_PLAN_KEY
            stmt = select(Plan).where(Plan.key == trial_plan_key)
            result = await self.session.execute(stmt)
            plan = result.scalar_one_or_none()
            if plan:
                return plan.id

        return subscription.plan_id

    async def get_entitlement(
        self,
        owner_id: uuid.UUID,
        account_type: BillingAccountType,
        feature_key: str,
    ) -> Optional[str]:
        account, subscription = await self._get_account_and_subscription(owner_id, account_type)
        if not account or not subscription:
            return None

        effective_plan_id = await self._resolve_effective_plan_id(subscription)

        stmt = (
            select(PlanEntitlement.value)
            .join(Feature)
            .where(
                and_(
                    PlanEntitlement.plan_id == effective_plan_id,
                    Feature.key == feature_key,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_remaining_quota(
        self,
        owner_id: uuid.UUID,
        account_type: BillingAccountType,
        feature_key: str,
    ) -> int:
        account, subscription = await self._get_account_and_subscription(owner_id, account_type)
        if not account or not subscription:
            return 0

        effective_plan_id = await self._resolve_effective_plan_id(subscription)

        stmt = (
            select(PlanEntitlement.value)
            .join(Feature)
            .where(
                and_(
                    PlanEntitlement.plan_id == effective_plan_id,
                    Feature.key == feature_key,
                )
            )
        )
        result = await self.session.execute(stmt)
        limit_str = result.scalar_one_or_none()

        if not limit_str:
            return 0

        try:
            limit = int(limit_str)
        except ValueError:
            return 0

        if limit == -1:
            return UNLIMITED_QUOTA

        stmt = (
            select(func.coalesce(func.sum(UsageRecord.quantity), 0))
            .join(Feature)
            .where(
                and_(
                    UsageRecord.account_id == account.id,
                    Feature.key == feature_key,
                    UsageRecord.subscription_id == subscription.id,
                    UsageRecord.period_start >= subscription.current_period_start,
                    UsageRecord.period_end <= subscription.current_period_end,  # pyright: ignore[reportOperatorIssue]
                )
            )
        )
        result = await self.session.execute(stmt)
        current_usage = result.scalar_one()

        return max(0, limit - current_usage)


def get_entitlement_resolver(session: AsyncSession) -> EntitlementResolver:
    """
    Dependency helper to get EntitlementResolver instance.
    """
    return EntitlementResolver(session)