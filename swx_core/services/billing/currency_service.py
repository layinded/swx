from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.currency import Currency, CurrencyCreate, CurrencyUpdate
from swx_core.repositories import currency_repository
from swx_core.repositories.currency_repository import CurrencyData


def _to_currency_data(data: CurrencyCreate | CurrencyUpdate) -> CurrencyData:
    return data.model_dump(exclude_none=True)  # pyright: ignore[reportReturnType]


async def create_currency(session: AsyncSession, data: CurrencyCreate) -> Currency:
    return await currency_repository.create(session, _to_currency_data(data))


async def list_currencies(session: AsyncSession, active_only: bool = False) -> list[Currency]:
    return await currency_repository.get_all(session, active_only)


async def get_currency_by_code(session: AsyncSession, code: str) -> Currency | None:
    return await currency_repository.get_by_code(session, code)


async def update_currency(session: AsyncSession, code: str, data: CurrencyUpdate) -> Currency | None:
    return await currency_repository.update(session, code, _to_currency_data(data))