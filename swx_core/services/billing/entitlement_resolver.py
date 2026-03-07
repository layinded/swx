"""
Entitlement Resolver
--------------------
Central service for resolving entitlements for actors (Users or Teams).
"""

import uuid
from typing import Optional, Union, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_
from datetime import datetime, timezone

from swx_core.models.billing import (
    BillingAccount, 
    BillingAccountType, 
    Subscription, 
    SubscriptionStatus, 
    Plan, 
    PlanEntitlement,
    Feature,
    UsageRecord
)
from swx_core.services.billing.feature_registry import FeatureRegistry, FeatureType
from swx_core.middleware.logging_middleware import logger

class EntitlementResolver:
    """
    Resolves if an actor has access to a feature.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def has(
        self, 
        owner_id: uuid.UUID, 
        account_type: BillingAccountType,
        feature_key: str,
    ) -> bool:
        """
        Check if an account has access to a feature.
        """
        entitlement = await self.get_entitlement(owner_id, account_type, feature_key)
        if not entitlement:
            return False

        feature_def = FeatureRegistry.get(feature_key)
        if not feature_def:
            logger.warning(f"Feature key '{feature_key}' not found in registry.")
            return False

        if feature_def.feature_type == FeatureType.BOOLEAN:
            return entitlement.lower() == "true"

        if feature_def.feature_type == FeatureType.QUOTA:
            # For quota, 'has' means 'has any remaining quota'
            remaining = await self.get_remaining_quota(owner_id, account_type, feature_key)
            return remaining > 0

        return False

    async def get_entitlement(
        self, 
        owner_id: uuid.UUID, 
        account_type: BillingAccountType,
        feature_key: str,
    ) -> Optional[str]:
        """
        Fetch the entitlement value for a feature.
        """
        # 1. Find the billing account
        stmt = select(BillingAccount).where(
            and_(
                BillingAccount.owner_id == owner_id,
                BillingAccount.account_type == account_type
            )
        )
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        
        if not account:
            # Fallback to default free plan if account doesn't exist?
            # For now, return None (fail closed)
            return None

        # 2. Find active subscription (including grace period)
        # ACTIVE and PAST_DUE (grace period) subscriptions allow access
        stmt = select(Subscription).where(
            and_(
                Subscription.account_id == account.id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]),
                # Ensure current time is within period
                # (Simplified for now, real world needs more complex time checks)
            )
        )
        result = await self.session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            return None

        # 3. Fetch plan entitlement
        stmt = (
            select(PlanEntitlement.value)
            .join(Feature)
            .where(
                and_(
                    PlanEntitlement.plan_id == subscription.plan_id,
                    Feature.key == feature_key
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
        """
        Calculate remaining quota for a feature.
        """
        # Get the limit from entitlement
        limit_str = await self.get_entitlement(owner_id, account_type, feature_key)
        if not limit_str:
            return 0
        
        try:
            limit = int(limit_str)
        except ValueError:
            return 0

        if limit == -1: # Infinite
            return 999999999

        # Get current usage
        # This requires finding the account and active subscription first
        stmt = select(BillingAccount).where(
            and_(
                BillingAccount.owner_id == owner_id,
                BillingAccount.account_type == account_type
            )
        )
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            return 0

        # Find usage record for current period
        stmt = (
            select(UsageRecord)
            .join(Feature)
            .where(
                and_(
                    UsageRecord.account_id == account.id,
                    Feature.key == feature_key,
                    # usage records should be linked to current subscription period
                )
            )
        )
        # Note: In a real system, we'd filter by the active subscription's current period.
        # For this implementation, we take the latest usage record.
        result = await self.session.execute(stmt)
        usage = result.scalar_one_or_none()
        
        current_usage = usage.quantity if usage else 0
        return max(0, limit - current_usage)

def get_entitlement_resolver(session: AsyncSession) -> EntitlementResolver:
    """
    Dependency helper to get EntitlementResolver instance.
    """
    return EntitlementResolver(session)
