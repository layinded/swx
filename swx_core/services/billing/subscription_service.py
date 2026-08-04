"""
Subscription Service
--------------------
Handles subscription lifecycle management.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, TypeGuard
from swx_core.utils.time import utc_now

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
    ACTIVE_STATUSES,  # pyright: ignore[reportAttributeAccessIssue]
    TERMINAL_STATUSES,  # pyright: ignore[reportAttributeAccessIssue]
)
from swx_core.middleware.logging_middleware import logger
from swx_core.events.dispatcher import event_bus

class SubscriptionService:
    """
    Manages the lifecycle of subscriptions.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _from_stripe_timestamp(timestamp: int | float) -> datetime:
        if isinstance(timestamp, bool):
            raise TypeError("Stripe timestamp must be int or float, not bool")
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    @staticmethod
    def _is_numeric_timestamp(value: object) -> TypeGuard[int | float]:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

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

    async def _commit_or_rollback(self, entity: object, error_msg: str) -> None:
        try:
            self.session.add(entity)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception(error_msg)
            raise

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
            self.session.add(account)
            await self._commit_or_rollback(account, f"Failed to create billing account for {account_type}:{owner_id}")
            await self.session.refresh(account)
            logger.info("Created new billing account for %s:%s", account_type, owner_id)

        return account

    async def _deactivate_active_subscriptions(self, account_id: uuid.UUID) -> list[str]:
        """Cancel any active subscriptions for an account (row-locked). Returns canceled subscription IDs."""
        stmt = select(Subscription).where(
            and_(
                Subscription.account_id == account_id,
                Subscription.status.in_(ACTIVE_STATUSES),  # pyright: ignore[reportAttributeAccessIssue]
            )
        ).with_for_update()
        result = await self.session.execute(stmt)
        ended_at = utc_now()
        canceled_ids: list[str] = []
        for sub in result.scalars().all():
            sub.status = SubscriptionStatus.CANCELED
            sub.ended_at = ended_at
            self.session.add(sub)
            canceled_ids.append(str(sub.id))
        return canceled_ids

    async def create_subscription(
        self, 
        account_id: uuid.UUID, 
        plan_key: str,
        stripe_subscription_id: Optional[str] = None
        ) -> Subscription:
        """Subscribe an account to a plan."""
        stmt = select(Plan).where(Plan.key == plan_key)
        result = await self.session.execute(stmt)
        plan = result.scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_key}' not found")

        canceled_ids = await self._deactivate_active_subscriptions(account_id)

        current_period_start = utc_now()
        subscription = Subscription(
            account_id=account_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=current_period_start,
            current_period_end=current_period_start + timedelta(days=BILLING_INTERVAL_DAYS.get(plan.billing_interval, 30)),
            stripe_subscription_id=stripe_subscription_id,
        )
        self.session.add(subscription)
        await self._commit_or_rollback(subscription, f"Failed to create subscription for account {account_id} and plan {plan_key}")
        await self.session.refresh(subscription)
        
        logger.info("Created subscription for account %s to plan %s", account_id, plan_key)
        if canceled_ids:
            await event_bus.dispatch("subscription.deactivated", payload={
                "account_id": str(account_id),
                "canceled_subscription_ids": canceled_ids,
            })
        await event_bus.dispatch("subscription.created", payload={
            "subscription_id": str(subscription.id),
            "account_id": str(account_id),
            "plan_key": plan_key,
            "status": SubscriptionStatus.ACTIVE.value,
        })
        return subscription

    async def cancel_subscription(self, subscription_id: uuid.UUID, immediate: bool = False):
        """Cancel a subscription (idempotent — skips if already canceled)."""
        subscription = await self.session.get(Subscription, subscription_id)
        if not subscription:
            return

        already_canceled = subscription.status == SubscriptionStatus.CANCELED
        if immediate:
            subscription.status = SubscriptionStatus.CANCELED
            if subscription.ended_at is None:
                subscription.ended_at = utc_now()
        else:
            subscription.cancel_at_period_end = True
            if subscription.canceled_at is None:
                subscription.canceled_at = utc_now()

        if already_canceled and not immediate and subscription.cancel_at_period_end:
            logger.info("Subscription %s already canceled at period end; skipping", subscription_id)
            return

        await self._commit_or_rollback(subscription, f"Failed to cancel subscription {subscription_id}")
        logger.info("Subscription %s canceled (immediate=%s)", subscription_id, immediate)
        await event_bus.dispatch("subscription.canceled", payload={
            "subscription_id": str(subscription_id),
            "immediate": immediate,
            "cancel_at_period_end": not immediate,
        })

    async def _sync_from_checkout_session(self, stripe_data: dict[str, object], checkout_id: str, depth: int = 0) -> None:
        """Fetch the full subscription object for a Checkout Session and retry sync."""
        if depth >= 2:
            logger.warning("sync_stripe_subscription: checkout %s exceeded recursion depth; aborting", checkout_id)
            return
        sub_id = stripe_data.get("subscription")
        if not isinstance(sub_id, str) or not sub_id:
            logger.info("sync_stripe_subscription: checkout %s has no 'subscription' id; nothing to sync", checkout_id)
            return
        from swx_core.services.billing.stripe_provider import get_stripe_provider
        provider = get_stripe_provider()
        if provider is None:
            logger.warning("sync_stripe_subscription: checkout %s references sub %s but Stripe provider not configured", checkout_id, sub_id)
            return
        try:
            fetched = await provider.get_subscription(sub_id)
        except Exception:
            logger.exception("sync_stripe_subscription: failed to fetch subscription %s for checkout %s", sub_id, checkout_id)
            return
        logger.info("sync_stripe_subscription: fetched subscription %s for checkout %s; retrying sync", sub_id, checkout_id)
        await self.sync_stripe_subscription(fetched, depth=depth + 1)

    async def _update_existing_subscription(
        self,
        subscription: Subscription,
        stripe_id: str,
        status: SubscriptionStatus,
        period_start: datetime,
        period_end: datetime,
        cancel_at_period_end: bool,
    ) -> None:
        subscription.status = status
        subscription.current_period_start = period_start
        subscription.current_period_end = period_end
        subscription.cancel_at_period_end = cancel_at_period_end
        if status == SubscriptionStatus.CANCELED and subscription.ended_at is None:
            subscription.ended_at = utc_now()
        if cancel_at_period_end and subscription.canceled_at is None:
            subscription.canceled_at = utc_now()

        await self._commit_or_rollback(subscription, f"Failed to sync existing Stripe subscription {stripe_id}")
        logger.info("Synced subscription %s from Stripe", stripe_id)
        await event_bus.dispatch("subscription.updated", payload={
            "subscription_id": str(subscription.id),
            "stripe_subscription_id": stripe_id,
            "status": status.value,
            "source": "stripe_webhook",
        })

    async def _create_subscription_from_stripe(
        self,
        stripe_data: dict[str, object],
        stripe_id: str,
        status: SubscriptionStatus,
        period_start: datetime,
        period_end: datetime,
        cancel_at_period_end: bool,
        stripe_price_id: Optional[str],
    ) -> None:
        customer_id = stripe_data.get("customer")
        if not isinstance(customer_id, str):
            logger.warning("No Stripe customer found for subscription %s", stripe_id)
            return

        if not stripe_price_id:
            logger.warning("No Stripe price found for subscription %s", stripe_id)
            return

        plan_stmt = select(Plan).where(Plan.stripe_price_id == stripe_price_id)
        plan = (await self.session.execute(plan_stmt)).scalar_one_or_none()
        if not plan:
            logger.warning("No local plan found for Stripe price %s", stripe_price_id)
            return

        account_stmt = select(BillingAccount).where(BillingAccount.stripe_customer_id == customer_id)
        account = (await self.session.execute(account_stmt)).scalar_one_or_none()
        if not account:
            logger.warning("No local account found for Stripe customer %s", customer_id)
            return

        canceled_ids = await self._deactivate_active_subscriptions(account.id)

        subscription = Subscription(
            account_id=account.id,
            plan_id=plan.id,
            status=status,
            stripe_subscription_id=stripe_id,
            current_period_start=period_start,
            current_period_end=period_end,
            cancel_at_period_end=cancel_at_period_end,
            canceled_at=utc_now() if cancel_at_period_end else None,
        )
        self.session.add(subscription)
        await self._commit_or_rollback(subscription, f"Failed to create Stripe subscription {stripe_id} from webhook")
        logger.info("Created subscription %s from Stripe webhook", stripe_id)
        if canceled_ids:
            await event_bus.dispatch("subscription.deactivated", payload={
                "account_id": str(account.id),
                "canceled_subscription_ids": canceled_ids,
            })
        await event_bus.dispatch("subscription.created", payload={
            "subscription_id": str(subscription.id),
            "account_id": str(account.id),
            "stripe_subscription_id": stripe_id,
            "status": status.value,
            "source": "stripe_webhook",
        })

    async def sync_stripe_subscription(self, stripe_data: dict[str, object], depth: int = 0):
        """Sync a subscription from Stripe webhook data (Subscription or Checkout Session)."""
        stripe_id = stripe_data.get("id")
        if not isinstance(stripe_id, str):
            logger.warning("sync_stripe_subscription: event data has no 'id'; skipping")
            return

        current_period_start = stripe_data.get("current_period_start")
        current_period_end = stripe_data.get("current_period_end")
        if not self._is_numeric_timestamp(current_period_start) or not self._is_numeric_timestamp(current_period_end):
            await self._sync_from_checkout_session(stripe_data, stripe_id, depth=depth)
            return

        stripe_status = stripe_data.get("status")
        if not isinstance(stripe_status, str):
            stripe_status = "active"

        cancel_at_period_end = stripe_data.get("cancel_at_period_end", False)
        if not isinstance(cancel_at_period_end, bool):
            cancel_at_period_end = False

        stmt = select(Subscription).where(Subscription.stripe_subscription_id == stripe_id)
        subscription = (await self.session.execute(stmt)).scalar_one_or_none()
        status = self._get_stripe_subscription_status(stripe_status)
        period_start = self._from_stripe_timestamp(current_period_start)
        period_end = self._from_stripe_timestamp(current_period_end)
        stripe_price_id = self._get_stripe_price_id(stripe_data)

        if subscription:
            await self._update_existing_subscription(
                subscription, stripe_id, status, period_start, period_end, cancel_at_period_end
            )
            return

        if status in TERMINAL_STATUSES:
            logger.info("sync_stripe_subscription: skipping insert of terminal-status subscription %s (status=%s)", stripe_id, stripe_status)
            return

        await self._create_subscription_from_stripe(
            stripe_data, stripe_id, status, period_start, period_end, cancel_at_period_end, stripe_price_id
        )

def get_subscription_service(session: AsyncSession) -> SubscriptionService:
    return SubscriptionService(session)
