"""
Subscription Service
--------------------
Handles subscription lifecycle management.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_

from swx_core.models.billing import (
    BillingAccount, 
    BillingAccountType, 
    Subscription, 
    SubscriptionStatus, 
    Plan
)
from swx_core.middleware.logging_middleware import logger

class SubscriptionService:
    """
    Manages the lifecycle of subscriptions.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_account(
        self, 
        owner_id: uuid.UUID, 
        account_type: BillingAccountType,
        billing_email: Optional[str] = None
    ) -> BillingAccount:
        """
        Ensures a billing account exists for the given owner.
        """
        stmt = select(BillingAccount).where(
            and_(
                BillingAccount.owner_id == owner_id,
                BillingAccount.account_type == account_type
            )
        )
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            account = BillingAccount(
                owner_id=owner_id,
                account_type=account_type,
                billing_email=billing_email
            )
            self.session.add(account)
            await self.session.commit()
            await self.session.refresh(account)
            logger.info(f"Created new billing account for {account_type}:{owner_id}")

        return account

    async def create_subscription(
        self, 
        account_id: uuid.UUID, 
        plan_key: str,
        stripe_subscription_id: Optional[str] = None
    ) -> Subscription:
        """
        Subscribes an account to a plan.
        """
        # 1. Get the plan
        stmt = select(Plan).where(Plan.key == plan_key)
        result = await self.session.execute(stmt)
        plan = result.scalar_one_or_none()
        if not plan:
            raise ValueError(f"Plan with key '{plan_key}' not found.")

        # 2. Deactivate existing active subscriptions
        stmt = select(Subscription).where(
            and_(
                Subscription.account_id == account_id,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        )
        result = await self.session.execute(stmt)
        active_subs = result.scalars().all()
        for sub in active_subs:
            sub.status = SubscriptionStatus.CANCELED
            sub.ended_at = datetime.utcnow()
            self.session.add(sub)

        # 3. Create new subscription
        subscription = Subscription(
            account_id=account_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30), # Default 30 days
            stripe_subscription_id=stripe_subscription_id
        )
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        
        logger.info(f"Created subscription for account {account_id} to plan {plan_key}")
        return subscription

    async def cancel_subscription(self, subscription_id: uuid.UUID, immediate: bool = False):
        """
        Cancels a subscription.
        """
        subscription = await self.session.get(Subscription, subscription_id)
        if not subscription:
            return

        if immediate:
            subscription.status = SubscriptionStatus.CANCELED
            subscription.ended_at = datetime.utcnow()
        else:
            subscription.cancel_at_period_end = True
            subscription.canceled_at = datetime.utcnow()

        self.session.add(subscription)
        await self.session.commit()
        logger.info(f"Subscription {subscription_id} canceled (immediate={immediate})")

    async def sync_stripe_subscription(self, stripe_data: dict):
        """
        Syncs a subscription state from Stripe webhook data.
        """
        stripe_id = stripe_data.get("id")
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "unpaid": SubscriptionStatus.UNPAID,
            "canceled": SubscriptionStatus.CANCELED,
            "incomplete": SubscriptionStatus.PAST_DUE,
            "incomplete_expired": SubscriptionStatus.EXPIRED,
            "trialing": SubscriptionStatus.TRIALING
        }
        
        stmt = select(Subscription).where(Subscription.stripe_subscription_id == stripe_id)
        result = await self.session.execute(stmt)
        subscription = result.scalar_one_or_none()
        
        if subscription:
            subscription.status = status_map.get(stripe_data.get("status"), SubscriptionStatus.ACTIVE)
            subscription.current_period_start = datetime.fromtimestamp(stripe_data.get("current_period_start"), tz=timezone.utc).replace(tzinfo=None)
            subscription.current_period_end = datetime.fromtimestamp(stripe_data.get("current_period_end"), tz=timezone.utc).replace(tzinfo=None)
            subscription.cancel_at_period_end = stripe_data.get("cancel_at_period_end", False)
            
            self.session.add(subscription)
            await self.session.commit()
            logger.info(f"Synced subscription {stripe_id} from Stripe")

def get_subscription_service(session: AsyncSession) -> SubscriptionService:
    return SubscriptionService(session)
