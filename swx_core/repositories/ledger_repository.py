# pyright: reportAny=false, reportUnknownVariableType=false

import uuid
from datetime import datetime
from typing import TypedDict
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, func, select

from swx_core.models.ledger import IdempotencyRecord, LedgerBalance, LedgerEntry


class LedgerEntryData(TypedDict, total=False):
    id: UUID
    account_id: UUID
    entry_type: str
    amount: int
    currency: str
    reference_type: str | None
    reference_id: str | None
    idempotency_key: str | None
    description: str | None
    metadata_: dict[str, str | int | float | bool | None]
    balance_after: int
    created_at: datetime
    created_by: UUID | None


class IdempotencyRecordData(TypedDict, total=False):
    id: UUID
    key: str
    account_id: UUID
    entry_id: UUID | None
    status: str
    created_at: datetime


def _entry_order() -> tuple[object, object]:
    return desc(LedgerEntry.created_at), desc(LedgerEntry.id)


async def create_entry(session: AsyncSession, data: LedgerEntryData) -> LedgerEntry:
    entry = LedgerEntry(**data)
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def get_entry_by_id(session: AsyncSession, entry_id: UUID) -> LedgerEntry | None:
    stmt = select(LedgerEntry).where(LedgerEntry.id == entry_id)  # pyright: ignore[reportArgumentType]
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_entries_by_account(session: AsyncSession, account_id: UUID, skip: int, limit: int) -> list[LedgerEntry]:
    stmt = select(LedgerEntry).where(LedgerEntry.account_id == account_id).order_by(*_entry_order()).offset(skip).limit(limit)  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())


async def get_filtered_entries(
    session: AsyncSession,
    account_id: UUID,
    *,
    entry_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[LedgerEntry]:
    stmt = select(LedgerEntry).where(LedgerEntry.account_id == account_id)  # pyright: ignore[reportArgumentType]
    if entry_type is not None:
        stmt = stmt.where(LedgerEntry.entry_type == entry_type)  # pyright: ignore[reportArgumentType]
    if date_from is not None:
        stmt = stmt.where(LedgerEntry.created_at >= date_from)  # pyright: ignore[reportArgumentType]
    if date_to is not None:
        stmt = stmt.where(LedgerEntry.created_at <= date_to)  # pyright: ignore[reportArgumentType]
    stmt = stmt.order_by(*_entry_order()).offset(skip).limit(limit)  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())


async def get_entries_by_reference(session: AsyncSession, account_id: UUID, reference_type: str, reference_id: str) -> list[LedgerEntry]:
    stmt = select(LedgerEntry).where(
        LedgerEntry.account_id == account_id,  # pyright: ignore[reportArgumentType]
        LedgerEntry.reference_type == reference_type,  # pyright: ignore[reportArgumentType]
        LedgerEntry.reference_id == reference_id,  # pyright: ignore[reportArgumentType]
    ).order_by(desc(LedgerEntry.created_at))
    return list((await session.execute(stmt)).scalars().all())


async def get_latest_entry(session: AsyncSession, account_id: UUID) -> LedgerEntry | None:
    stmt = select(LedgerEntry).where(LedgerEntry.account_id == account_id).order_by(*_entry_order()).limit(1)  # pyright: ignore[reportArgumentType]
    return (await session.execute(stmt)).scalars().first()


async def count_entries(session: AsyncSession, account_id: UUID) -> int:
    stmt = select(func.count(LedgerEntry.id)).where(LedgerEntry.account_id == account_id)  # pyright: ignore[reportArgumentType]
    return int((await session.execute(stmt)).scalar() or 0)


async def get_balance(session: AsyncSession, account_id: UUID) -> LedgerBalance | None:
    stmt = select(LedgerBalance).where(LedgerBalance.account_id == account_id)  # pyright: ignore[reportArgumentType]
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_balance(session: AsyncSession, account_id: UUID, balance: int, last_entry_id: UUID | None, currency: str = "USD") -> LedgerBalance:
    stmt = insert(LedgerBalance).values(
        id=uuid.uuid4(),
        account_id=account_id,
        currency=currency,
        balance=balance,
        last_entry_id=last_entry_id,
    ).on_conflict_do_update(
        index_elements=["account_id"],
        set_={"currency": currency, "balance": balance, "last_entry_id": last_entry_id},
    )
    await session.execute(stmt)
    balance_row = await get_balance(session, account_id)
    if balance_row is None:
        raise ValueError("Ledger balance upsert failed")
    return balance_row


async def get_idempotency_record(session: AsyncSession, key: str) -> IdempotencyRecord | None:
    stmt = select(IdempotencyRecord).where(IdempotencyRecord.key == key)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_idempotency_record(session: AsyncSession, data: IdempotencyRecordData) -> IdempotencyRecord:
    record = IdempotencyRecord(**data)
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


async def sum_entries(session: AsyncSession, account_id: UUID, entry_type: str) -> int:
    stmt = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
        LedgerEntry.account_id == account_id,  # pyright: ignore[reportArgumentType]
        LedgerEntry.entry_type == entry_type,  # pyright: ignore[reportArgumentType]
    )
    return int((await session.execute(stmt)).scalar() or 0)
