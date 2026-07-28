# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false

from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.webhook_delivery import WebhookDelivery
from swx_core.models.webhook_endpoint import WebhookEndpoint
from swx_core.models.webhook_event import WebhookEventSubscription


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _apply(instance: Any, data: dict[str, Any]) -> Any:
    for key, value in data.items():
        setattr(instance, key, value)
    return instance


async def create_webhook_endpoint(session: AsyncSession, data: dict[str, Any]) -> WebhookEndpoint:
    endpoint = WebhookEndpoint(**data)
    session.add(endpoint)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint


async def get_webhook_endpoint_by_id(session: AsyncSession, endpoint_id: UUID) -> WebhookEndpoint | None:
    return await session.get(WebhookEndpoint, endpoint_id)


async def list_webhook_endpoints(session: AsyncSession, *, user_id: UUID | None = None, is_active: bool | None = None, skip: int = 0, limit: int = 100) -> list[WebhookEndpoint]:
    stmt = select(WebhookEndpoint)
    if user_id is not None:
        stmt = stmt.where(WebhookEndpoint.user_id == user_id)
    if is_active is not None:
        stmt = stmt.where(WebhookEndpoint.is_active == is_active)  # pyright: ignore[reportArgumentType]
    stmt = stmt.order_by(WebhookEndpoint.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_webhook_endpoint(session: AsyncSession, endpoint_id: UUID, data: dict[str, Any]) -> WebhookEndpoint | None:
    endpoint = await get_webhook_endpoint_by_id(session, endpoint_id)
    if endpoint is None:
        return None
    updated_endpoint = _apply(endpoint, {**data, "updated_at": utc_now_naive()})
    session.add(updated_endpoint)
    await session.commit()
    await session.refresh(endpoint)
    return endpoint


async def upsert_webhook_subscriptions(session: AsyncSession, endpoint_id: UUID, event_types: list[str], is_active: bool) -> list[WebhookEventSubscription]:
    stmt = select(WebhookEventSubscription).where(WebhookEventSubscription.endpoint_id == endpoint_id, WebhookEventSubscription.event_type.in_(event_types))  # pyright: ignore[reportArgumentType]
    existing = {item.event_type: item for item in (await session.execute(stmt)).scalars().all()}
    saved: list[WebhookEventSubscription] = []
    for event_type in event_types:
        match = existing.get(event_type)
        entity = WebhookEventSubscription(endpoint_id=endpoint_id, event_type=event_type, is_active=is_active) if match is None else _apply(match, {"is_active": is_active})
        session.add(entity)
        saved.append(entity)
    await session.commit()
    for item in saved:
        await session.refresh(item)
    return saved


async def list_webhook_subscriptions(session: AsyncSession, endpoint_id: UUID, *, is_active: bool | None = None) -> list[WebhookEventSubscription]:
    stmt = select(WebhookEventSubscription).where(WebhookEventSubscription.endpoint_id == endpoint_id)
    if is_active is not None:
        stmt = stmt.where(WebhookEventSubscription.is_active == is_active)  # pyright: ignore[reportArgumentType]
    stmt = stmt.order_by(WebhookEventSubscription.event_type)
    return list((await session.execute(stmt)).scalars().all())


async def create_webhook_delivery(session: AsyncSession, data: dict[str, Any]) -> WebhookDelivery:
    delivery = WebhookDelivery(**data)
    session.add(delivery)
    await session.commit()
    await session.refresh(delivery)
    return delivery


async def get_webhook_delivery_by_id(session: AsyncSession, delivery_id: UUID) -> WebhookDelivery | None:
    return await session.get(WebhookDelivery, delivery_id)


async def update_webhook_delivery(session: AsyncSession, delivery_id: UUID, data: dict[str, Any]) -> WebhookDelivery | None:
    delivery = await get_webhook_delivery_by_id(session, delivery_id)
    if delivery is None:
        return None
    session.add(_apply(delivery, data))
    await session.commit()
    await session.refresh(delivery)
    return delivery


async def list_webhook_deliveries(session: AsyncSession, *, user_id: UUID | None = None, endpoint_id: UUID | None = None, status: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None, skip: int = 0, limit: int = 100) -> list[WebhookDelivery]:
    stmt = select(WebhookDelivery).join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)  # pyright: ignore[reportArgumentType]
    if user_id is not None:
        stmt = stmt.where(WebhookEndpoint.user_id == user_id)
    if endpoint_id is not None:
        stmt = stmt.where(WebhookDelivery.endpoint_id == endpoint_id)
    if status is not None:
        stmt = stmt.where(WebhookDelivery.status == status)
    if start_date is not None:
        stmt = stmt.where(WebhookDelivery.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(WebhookDelivery.created_at <= end_date)
    stmt = stmt.order_by(WebhookDelivery.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_pending_deliveries_for_retry(session: AsyncSession, now: datetime, limit: int = 100) -> list[WebhookDelivery]:
    next_retry_at = cast(Any, WebhookDelivery.next_retry_at)
    stmt = select(WebhookDelivery).where(WebhookDelivery.status == "retrying", next_retry_at.is_not(None), next_retry_at <= now).order_by(next_retry_at).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def count_webhook_deliveries_by_status(session: AsyncSession, *, user_id: UUID | None = None, endpoint_id: UUID | None = None) -> dict[str, int]:
    stmt = select(WebhookDelivery.status, func.count()).join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id).group_by(WebhookDelivery.status)  # pyright: ignore[reportArgumentType]
    if user_id is not None:
        stmt = stmt.where(WebhookEndpoint.user_id == user_id)
    if endpoint_id is not None:
        stmt = stmt.where(WebhookDelivery.endpoint_id == endpoint_id)
    rows = (await session.execute(stmt)).all()
    return {str(status): int(count) for status, count in rows}
