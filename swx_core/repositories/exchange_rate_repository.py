# pyright: reportAny=false, reportUnknownVariableType=false

from datetime import datetime
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, select

from swx_core.models.currency import ExchangeRate


class ExchangeRateData(TypedDict, total=False):
    base_currency: str
    quote_currency: str
    rate: float
    source: str | None
    fetched_at: datetime


async def create(session: AsyncSession, data: ExchangeRateData) -> ExchangeRate:
    rate = ExchangeRate(**data)
    session.add(rate)
    await session.commit()
    await session.refresh(rate)
    return rate


async def get_latest(session: AsyncSession, base: str, quote: str) -> ExchangeRate | None:
    base_code = base.upper()
    quote_code = quote.upper()
    stmt = select(ExchangeRate).where(
        ExchangeRate.base_currency == base_code,
        ExchangeRate.quote_currency == quote_code,
    ).order_by(desc(ExchangeRate.fetched_at), desc(ExchangeRate.created_at)).limit(1)
    return (await session.execute(stmt)).scalars().first()


async def get_all_for_base(session: AsyncSession, base: str) -> list[ExchangeRate]:
    base_code = base.upper()
    stmt = select(ExchangeRate).where(ExchangeRate.base_currency == base_code).order_by(ExchangeRate.quote_currency, desc(ExchangeRate.fetched_at))
    return list((await session.execute(stmt)).scalars().all())


async def get_rates_map(session: AsyncSession, base: str) -> dict[str, float]:
    rates: dict[str, float] = {}
    for rate in await get_all_for_base(session, base):
        if rate.quote_currency not in rates:
            rates[rate.quote_currency] = rate.rate
    return rates
