from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.billing import (
    BillingAccountType,
    Subscription,
    SubscriptionPublic,
)
from swx_core.repositories import billing_repository
from swx_core.services.billing.subscription_service import SubscriptionService
from swx_core.utils.errors import ForbiddenError, NotFoundError


async def _enrich_subscription(session: AsyncSession, subscription: Subscription) -> SubscriptionPublic:
    plan = await billing_repository.get_plan_by_id(session, subscription.plan_id)
    plan_key = plan.key if plan else ""
    plan_name = plan.name if plan else None
    return SubscriptionPublic(
        id=subscription.id,
        plan_id=subscription.plan_id,
        plan_key=plan_key,
        plan_name=plan_name,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        canceled_at=subscription.canceled_at,
        ended_at=subscription.ended_at,
        trial_ends_at=subscription.trial_ends_at,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
    )


async def get_current_subscription_controller(
    session: AsyncSession, user_id: UUID
) -> SubscriptionPublic:
    sub_service = SubscriptionService(session)
    account = await sub_service.get_or_create_account(user_id, BillingAccountType.USER)
    subscription = await sub_service.get_active_subscription(account.id)
    if subscription is None:
        raise NotFoundError("Subscription")
    return await _enrich_subscription(session, subscription)


async def list_subscriptions_controller(
    session: AsyncSession, user_id: UUID, skip: int, limit: int
) -> list[SubscriptionPublic]:
    sub_service = SubscriptionService(session)
    account = await sub_service.get_or_create_account(user_id, BillingAccountType.USER)
    subscriptions = await sub_service.list_subscriptions(account.id, skip, limit)
    return [await _enrich_subscription(session, sub) for sub in subscriptions]


async def create_subscription_controller(
    session: AsyncSession, user_id: UUID, plan_key: str
) -> SubscriptionPublic:
    sub_service = SubscriptionService(session)
    account = await sub_service.get_or_create_account(user_id, BillingAccountType.USER)
    subscription = await sub_service.create_subscription(account.id, plan_key)
    return await _enrich_subscription(session, subscription)


async def cancel_subscription_controller(
    session: AsyncSession, user_id: UUID, subscription_id: UUID, immediate: bool
) -> SubscriptionPublic:
    sub_service = SubscriptionService(session)
    subscription = await sub_service.get_subscription_by_id(subscription_id)
    if subscription is None:
        raise NotFoundError("Subscription", str(subscription_id))

    if subscription.account.owner_id != user_id:
        raise ForbiddenError("Subscription does not belong to this user")

    await sub_service.cancel_subscription(subscription_id, immediate=immediate)
    await session.refresh(subscription)
    return await _enrich_subscription(session, subscription)
