from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy import and_

from swx_core.models.billing import (
    BillingAccount,
    BillingAccountType,
    Subscription,
    SubscriptionStatus,
    Plan,
    ACTIVE_STATUSES,
)


async def get_user_billing_account(
    session: AsyncSession, user_id: UUID
) -> Optional[BillingAccount]:
    stmt = select(BillingAccount).where(
        and_(
            BillingAccount.owner_id == user_id,  # pyright: ignore[reportArgumentType]
            BillingAccount.account_type == BillingAccountType.USER,  # pyright: ignore[reportArgumentType]
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_active_subscription(
    session: AsyncSession, account_id: UUID
) -> Optional[Subscription]:
    stmt = select(Subscription).where(
        and_(
            Subscription.account_id == account_id,  # pyright: ignore[reportArgumentType]
            Subscription.status.in_(ACTIVE_STATUSES),  # pyright: ignore[reportAttributeAccessIssue]
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_plan_by_id(
    session: AsyncSession, plan_id: UUID
) -> Optional[Plan]:
    return await session.get(Plan, plan_id)


def is_subscription_expired(sub: Subscription) -> bool:
    if not sub.current_period_end:
        return False
    end = sub.current_period_end
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > end
