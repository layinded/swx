import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.repositories import inbound_webhook_delivery_repository


def _payload_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


async def check_and_record(
    session: AsyncSession,
    provider: str,
    event_id: str,
    payload: bytes,
    reference: str | None = None,
    redis_client=None,
) -> bool:
    """Check if an inbound webhook has already been processed.

    Uses Redis as a fast-path cache, then falls back to the durable
    ``swx_inbound_webhook_delivery`` table as the source of truth.

    Returns ``True`` if this is a NEW delivery (should process),
    ``False`` if it's a duplicate (already processed).
    """
    dedup_key = f"webhook:{provider}:idempotency:{event_id}"

    if redis_client is not None:
        if await redis_client.exists(dedup_key):
            return False

    already = await inbound_webhook_delivery_repository.is_processed(session, provider, event_id)
    if already:
        return False

    await inbound_webhook_delivery_repository.mark_processed(
        session, provider, event_id, _payload_hash(payload), reference
    )

    if redis_client is not None:
        await redis_client.setex(dedup_key, 604800, provider)

    return True