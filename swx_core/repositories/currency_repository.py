# pyright: reportAny=false, reportUnknownVariableType=false

from datetime import datetime
from typing import TypedDict
from swx_core.utils.time import utc_now

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.currency import Currency
from swx_core.models.currency import CurrencyStatus

class CurrencyData(TypedDict, total=False):
    code: str
    name: str
    symbol: str
    decimals: int
    is_base: bool
    status: str
    minimum_amount: int
    supported_providers: list[str]
    extra_data: dict[str, object]
    updated_at: datetime

async def create(session: AsyncSession, data: CurrencyData) -> Currency:
    currency = Currency(**data)
    session.add(currency)
    await session.commit()
    await session.refresh(currency)
    return currency

async def get_by_code(session: AsyncSession, code: str) -> Currency | None:
    stmt = select(Currency).where(Currency.code == code.upper())
    return (await session.execute(stmt)).scalar_one_or_none()

async def get_all(session: AsyncSession, active_only: bool = False) -> list[Currency]:
    stmt = select(Currency)
    if active_only:
        stmt = stmt.where(Currency.status == CurrencyStatus.ACTIVE.value)
    stmt = stmt.order_by(Currency.code)
    return list((await session.execute(stmt)).scalars().all())

async def get_base_currency(session: AsyncSession) -> Currency | None:
    stmt = select(Currency).where(Currency.is_base)
    return (await session.execute(stmt)).scalar_one_or_none()

async def update(session: AsyncSession, code: str, data: CurrencyData) -> Currency | None:
    currency = await get_by_code(session, code)
    if currency is None:
        return None
    payload = dict(data)
    payload["updated_at"] = utc_now()
    for key, value in payload.items():
        setattr(currency, key, value)
    session.add(currency)
    await session.commit()
    await session.refresh(currency)
    return currency
