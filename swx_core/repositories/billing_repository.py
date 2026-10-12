from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.billing import (
    ACTIVE_STATUSES,
    BillingAccount,
    BillingAccountType,
    Plan,
    Subscription,
)
from swx_core.models.credit_pack import CreditPack


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


async def get_subscription_by_id(
    session: AsyncSession, subscription_id: UUID
) -> Optional[Subscription]:
    return await session.get(Subscription, subscription_id)


async def get_plan_by_id(
    session: AsyncSession, plan_id: UUID
) -> Optional[Plan]:
    return await session.get(Plan, plan_id)


async def get_plan_by_key(
    session: AsyncSession, plan_key: str
) -> Optional[Plan]:
    stmt = select(Plan).where(Plan.key == plan_key)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_public_plans(
    session: AsyncSession
) -> list[Plan]:
    stmt = select(Plan).where(
        and_(
            Plan.is_public == True,  # pyright: ignore[reportArgumentType]
            Plan.is_active == True,  # pyright: ignore[reportArgumentType]
        )
    ).order_by(Plan.created_at)  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())


async def get_credit_pack_by_key(
    session: AsyncSession, pack_key: str
) -> Optional[CreditPack]:
    stmt = select(CreditPack).where(CreditPack.key == pack_key)  # pyright: ignore[reportArgumentType]
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_public_credit_packs(
    session: AsyncSession
) -> list[CreditPack]:
    stmt = select(CreditPack).where(
        and_(
            CreditPack.is_public == True,  # pyright: ignore[reportArgumentType]
            CreditPack.is_active == True,  # pyright: ignore[reportArgumentType]
        )
    ).order_by(CreditPack.tokens)  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())


async def get_subscriptions_by_account(
    session: AsyncSession, account_id: UUID, skip: int, limit: int
) -> list[Subscription]:
    stmt = (
        select(Subscription)
        .where(Subscription.account_id == account_id)  # pyright: ignore[reportArgumentType]
        .order_by(Subscription.created_at.desc())  # pyright: ignore[reportArgumentType]
        .offset(skip)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


def is_subscription_expired(sub: Subscription) -> bool:
    if not sub.current_period_end:
        return False
    end = sub.current_period_end
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > end


async def get_billing_account_by_owner(
    session: AsyncSession, owner_id: UUID, account_type: BillingAccountType
) -> Optional[BillingAccount]:
    stmt = select(BillingAccount).where(
        and_(
            BillingAccount.owner_id == owner_id,  # pyright: ignore[reportArgumentType]
            BillingAccount.account_type == account_type,  # pyright: ignore[reportArgumentType]
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_billing_account_by_stripe_customer(
    session: AsyncSession, stripe_customer_id: str
) -> Optional[BillingAccount]:
    stmt = select(BillingAccount).where(BillingAccount.stripe_customer_id == stripe_customer_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_plan_by_stripe_price_id(
    session: AsyncSession, stripe_price_id: str
) -> Optional[Plan]:
    stmt = select(Plan).where(Plan.stripe_price_id == stripe_price_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_subscription_by_stripe_id(
    session: AsyncSession, stripe_subscription_id: str
) -> Optional[Subscription]:
    stmt = select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_active_subscriptions_for_update(
    session: AsyncSession, account_id: UUID
) -> list[Subscription]:
    stmt = select(Subscription).where(
        and_(
            Subscription.account_id == account_id,  # pyright: ignore[reportArgumentType]
            Subscription.status.in_(ACTIVE_STATUSES),  # pyright: ignore[reportAttributeAccessIssue]
        )
    ).with_for_update()
    result = await session.execute(stmt)
    return list(result.scalars().all())
