from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.models.currency import ExchangeRatePublic
from swx_core.repositories import currency_repository, exchange_rate_repository
from swx_core.repositories.exchange_rate_repository import ExchangeRateData


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _manual_rates(base: str) -> dict[str, float]:
    defaults = {"USD": {"NGN": 1500.0, "KES": 129.5, "ZAR": 18.2, "GHS": 15.4}}
    return defaults.get(base.upper(), {})


def _manual_rate_payload(base: str, quote: str, rate: float) -> ExchangeRateData:
    return {"base_currency": base.upper(), "quote_currency": quote.upper(), "rate": rate, "source": "manual", "fetched_at": utc_now_naive()}


async def get_rate(session: AsyncSession, base: str, quote: str) -> float:
    source = base.upper()
    target = quote.upper()
    if source == target:
        return 1.0
    direct = await exchange_rate_repository.get_latest(session, source, target)
    if direct is not None:
        return direct.rate
    inverse = await exchange_rate_repository.get_latest(session, target, source)
    if inverse is not None and inverse.rate != 0:
        return 1 / inverse.rate
    pivot = (await currency_repository.get_base_currency(session)) or await currency_repository.get_by_code(session, settings.DEFAULT_BASE_CURRENCY)
    pivot_code = pivot.code if pivot is not None else settings.DEFAULT_BASE_CURRENCY
    if source != pivot_code and target != pivot_code:
        pivot_rates = await exchange_rate_repository.get_rates_map(session, pivot_code)
        if source in pivot_rates and target in pivot_rates and pivot_rates[source] != 0:
            return pivot_rates[target] / pivot_rates[source]
    raise HTTPException(status_code=404, detail=f"Exchange rate not found for {source}/{target}")


async def convert(session: AsyncSession, amount_nano: int, from_currency: str, to_currency: str) -> int:
    rate = await get_rate(session, from_currency, to_currency)
    return int(round(amount_nano * rate))


async def sync_rates(session: AsyncSession, base: str = "USD") -> dict[str, float]:
    base_code = base.upper()
    rates = _manual_rates(base_code)
    for quote, rate in rates.items():
        _ = await exchange_rate_repository.create(session, _manual_rate_payload(base_code, quote, rate))
    return rates


async def set_manual_rate(session: AsyncSession, base: str, quote: str, rate: float) -> ExchangeRatePublic:
    if rate <= 0:
        raise HTTPException(status_code=400, detail="Exchange rate must be greater than zero")
    entry = await exchange_rate_repository.create(session, _manual_rate_payload(base, quote, rate))
    return ExchangeRatePublic.model_validate(entry)
