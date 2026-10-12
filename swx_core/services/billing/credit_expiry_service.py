from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.models.credit_lot import CreditLot
from swx_core.utils.time import utc_now


async def create_lot(
    session: AsyncSession,
    account_id: UUID,
    source: str,
    tokens: int,
    reference: str,
    expires_at: datetime | None = None,
) -> CreditLot:
    lot = CreditLot(
        account_id=account_id,
        source=source,
        tokens_total=tokens,
        reference=reference,
        expires_at=expires_at,
    )
    session.add(lot)
    await session.commit()
    await session.refresh(lot)
    logger.info("Credit lot created: %d %s tokens for %s (expires=%s)", tokens, source, account_id, expires_at)
    await event_bus.dispatch("credit_lot.created", payload={
        "lot_id": str(lot.id),
        "account_id": str(account_id),
        "source": source,
        "tokens": tokens,
    })
    return lot


async def consume_fifo(session: AsyncSession, account_id: UUID, tokens: int) -> list[CreditLot]:
    """Consume tokens from credit lots in FIFO order (bonus first, then purchased)."""
    stmt = (
        select(CreditLot)
        .where(
            CreditLot.account_id == account_id,  # pyright: ignore[reportArgumentType]
            CreditLot.tokens_consumed < CreditLot.tokens_total,  # pyright: ignore[reportArgumentType]
        )
        .order_by(CreditLot.source, CreditLot.created_at)  # pyright: ignore[reportArgumentType]
    )
    lots = list((await session.execute(stmt)).scalars().all())
    consumed_lots: list[CreditLot] = []
    remaining = tokens
    for lot in lots:
        if remaining <= 0:
            break
        available = lot.tokens_total - lot.tokens_consumed
        take = min(available, remaining)
        lot.tokens_consumed += take
        remaining -= take
        session.add(lot)
        consumed_lots.append(lot)
    await session.commit()
    if consumed_lots:
        await event_bus.dispatch("credit_lot.consumed", payload={
            "account_id": str(account_id),
            "tokens_requested": tokens,
            "lots_affected": len(consumed_lots),
        })
    return consumed_lots


async def expire_stale_lots(session: AsyncSession) -> int:
    """Mark expired lots as fully consumed. Returns count of expired lots."""
    now = utc_now()
    stmt = select(CreditLot).where(
        CreditLot.expires_at.isnot(None),  # pyright: ignore[reportAttributeAccessIssue,reportOptionalMemberAccess]
        CreditLot.expires_at < now,  # pyright: ignore[reportOptionalOperand,reportArgumentType]
        CreditLot.tokens_consumed < CreditLot.tokens_total,  # pyright: ignore[reportArgumentType]
    )
    lots = list((await session.execute(stmt)).scalars().all())
    for lot in lots:
        lot.tokens_consumed = lot.tokens_total
        session.add(lot)
    await session.commit()
    if lots:
        logger.info("Expired %d stale credit lots", len(lots))
        await event_bus.dispatch("credit_lots.expired", payload={"count": len(lots)})
    return len(lots)