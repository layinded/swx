from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.config.settings import settings
from swx_core.models.inbound_webhook_delivery import InboundWebhookDelivery
from swx_core.utils.time import utc_now


async def is_processed(
    session: AsyncSession, provider: str, event_id: str
) -> bool:
    stmt = select(InboundWebhookDelivery.id).where(
        InboundWebhookDelivery.provider == provider,  # pyright: ignore[reportArgumentType]
        InboundWebhookDelivery.event_id == event_id,  # pyright: ignore[reportArgumentType]
    ).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def mark_processed(
    session: AsyncSession,
    provider: str,
    event_id: str,
    payload_hash: str,
    reference: str | None = None,
) -> InboundWebhookDelivery:
    delivery = InboundWebhookDelivery(
        provider=provider,
        event_id=event_id,
        reference=reference,
        payload_hash=payload_hash,
    )
    session.add(delivery)
    await session.flush()
    await session.commit()
    return delivery


async def cleanup_expired(
    session: AsyncSession, retention_days: int | None = None
) -> int:
    days = retention_days if retention_days is not None else settings.WEBHOOK_RETENTION_DAYS
    cutoff = utc_now() - timedelta(days=days)
    stmt = select(InboundWebhookDelivery).where(
        InboundWebhookDelivery.created_at < cutoff  # pyright: ignore[reportArgumentType]
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    for row in rows:
        await session.delete(row)
    await session.commit()
    return len(rows)