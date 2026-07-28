"""
Subscription Service
--------------------
Handles subscription lifecycle management.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlmodel import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.billing import (
    BillingAccount, 
    BillingAccountType, 
    Subscription, 
    SubscriptionStatus, 
    Plan,
    BILLING_INTERVAL_DAYS,
)
from swx_core.middleware.logging_middleware import logger

class SubscriptionService:
    """
    Manages the lifecycle of subscriptions.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _utc_now_naive() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _from_stripe_timestamp(timestamp: int | float) -> datetime:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _get_stripe_subscription_status(stripe_status: str) -> SubscriptionStatus:
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "unpaid": SubscriptionStatus.UNPAID,
            "canceled": SubscriptionStatus.CANCELED,
            "incomplete": SubscriptionStatus.PAST_DUE,
            "incomplete_expired": SubscriptionStatus.EXPIRED,
            "trialing": SubscriptionStatus.TRIALING,
        }
        return status_map.get(stripe_status, SubscriptionStatus.ACTIVE)

    @staticmethod
    def _get_stripe_price_id(stripe_data: dict[str, object]) -> Optional[str]:
        stripe_plan = stripe_data.get("plan")
        if isinstance(stripe_plan, dict):
            plan_id = stripe_plan.get("id")
            if isinstance(plan_id, str):
                return plan_id

        stripe_items = stripe_data.get("items")
        if not isinstance(stripe_items, dict):
            return None

        item_rows = stripe_items.get("data")
        if not isinstance(item_rows, list) or not item_rows:
            return None

        first_item = item_rows[0]
        if not isinstance(first_item, dict):
            return None

        stripe_price = first_item.get("price")
        if not isinstance(stripe_price, dict):
            return None

        price_id = stripe_price.get("id")
        return price_id if isinstance(price_id, str) else None

    async def get_or_create_account(
        self, 
        owner_id: uuid.UUID, 
        account_type: BillingAccountType,
        billing_email: Optional[str] = None
    ) -> BillingAccount:
        """
        Ensures a billing account exists for the given owner.
        """
        stmt = select(BillingAccount).where(and_(BillingAccount.owner_id == owner_id, BillingAccount.account_type == account_type))
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            account = BillingAccount(owner_id=owner_id, account_type=account_type, billing_email=billing_email)
            try:
                self.session.add(account)
                await self.session.commit()
                await self.session.refresh(account)
            except Exception:
                await self.session.rollback()
                logger.exception("Failed to create billing account for %s:%s", account_type, owner_id)
                raise
            logger.info("Created new billing account for %s:%s", account_type, owner_id)

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
            raise HTTPException(status_code=404, detail=f"Plan '{plan_key}' not found")

        # 2. Deactivate existing active subscriptions
        stmt = select(Subscription).where(and_(Subscription.account_id == account_id, Subscription.status == SubscriptionStatus.ACTIVE)).with_for_update()
        result = await self.session.execute(stmt)
        active_subs = result.scalars().all()
        ended_at = self._utc_now_naive()
        for active_subscription in active_subs:
            active_subscription.status = SubscriptionStatus.CANCELED
            active_subscription.ended_at = ended_at
            self.session.add(active_subscription)

        current_period_start = self._utc_now_naive()
        subscription = Subscription(
            account_id=account_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=current_period_start,
            current_period_end=current_period_start + timedelta(days=BILLING_INTERVAL_DAYS.get(plan.billing_interval, 30)),
            stripe_subscription_id=stripe_subscription_id,
        )
        try:
            self.session.add(subscription)
            await self.session.commit()
            await self.session.refresh(subscription)
        except Exception:
            await self.session.rollback()
            logger.exception("Failed to create subscription for account %s and plan %s", account_id, plan_key)
            raise
        
        logger.info("Created subscription for account %s to plan %s", account_id, plan_key)
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
            subscription.ended_at = self._utc_now_naive()
        else:
            subscription.cancel_at_period_end = True
            subscription.canceled_at = self._utc_now_naive()

        try:
            self.session.add(subscription)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception("Failed to cancel subscription %s", subscription_id)
            raise
        logger.info("Subscription %s canceled (immediate=%s)", subscription_id, immediate)

    async def sync_stripe_subscription(self, stripe_data: dict[str, object]):
        """
        Syncs a subscription state from Stripe webhook data.
        """
        stripe_id = stripe_data.get("id")
        if not isinstance(stripe_id, str):
            return

        current_period_start = stripe_data.get("current_period_start")
        current_period_end = stripe_data.get("current_period_end")
        if not isinstance(current_period_start, (int, float)) or not isinstance(current_period_end, (int, float)):
            return

        stripe_status = stripe_data.get("status")
        if not isinstance(stripe_status, str):
            stripe_status = "active"

        cancel_at_period_end = stripe_data.get("cancel_at_period_end", False)
        if not isinstance(cancel_at_period_end, bool):
            cancel_at_period_end = False

        stmt = select(Subscription).where(Subscription.stripe_subscription_id == stripe_id)
        result = await self.session.execute(stmt)
        subscription = result.scalar_one_or_none()
        status = self._get_stripe_subscription_status(stripe_status)
        period_start = self._from_stripe_timestamp(current_period_start)
        period_end = self._from_stripe_timestamp(current_period_end)
        stripe_price_id = self._get_stripe_price_id(stripe_data)

        if subscription:
            subscription.status = status
            subscription.current_period_start = period_start
            subscription.current_period_end = period_end
            subscription.cancel_at_period_end = cancel_at_period_end

            try:
                self.session.add(subscription)
                await self.session.commit()
            except Exception:
                await self.session.rollback()
                logger.exception("Failed to sync existing Stripe subscription %s", stripe_id)
                raise
            logger.info("Synced subscription %s from Stripe", stripe_id)
            return

        customer_id = stripe_data.get("customer")
        if not isinstance(customer_id, str):
            logger.warning("No Stripe customer found for subscription %s", stripe_id)
            return

        if not stripe_price_id:
            logger.warning("No Stripe price found for subscription %s", stripe_id)
            return

        plan_stmt = select(Plan).where(Plan.stripe_price_id == stripe_price_id)
        plan_result = await self.session.execute(plan_stmt)
        plan = plan_result.scalar_one_or_none()

        if not plan:
            logger.warning("No local plan found for Stripe price %s", stripe_price_id)
            return

        account_stmt = select(BillingAccount).where(
            BillingAccount.stripe_customer_id == customer_id
        )
        account_result = await self.session.execute(account_stmt)
        account = account_result.scalar_one_or_none()

        if not account:
            logger.warning("No local account found for Stripe customer %s", customer_id)
            return

        subscription = Subscription(
            account_id=account.id,
            plan_id=plan.id,
            status=status,
            stripe_subscription_id=stripe_id,
            current_period_start=period_start,
            current_period_end=period_end,
            cancel_at_period_end=cancel_at_period_end,
        )
        try:
            self.session.add(subscription)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception("Failed to create Stripe subscription %s from webhook", stripe_id)
            raise
        logger.info("Created subscription %s from Stripe webhook", stripe_id)

def get_subscription_service(session: AsyncSession) -> SubscriptionService:
    return SubscriptionService(session)
