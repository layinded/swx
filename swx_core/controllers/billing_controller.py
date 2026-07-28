from fastapi import HTTPException
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.currency import ConvertResponse, CurrencyCreate, CurrencyPublic, CurrencyUpdate, ExchangeRatePublic, WalletPublic
from swx_core.repositories import currency_repository, exchange_rate_repository
from swx_core.services.billing import exchange_rate_service, tax_service, wallet_service
from swx_core.services.billing.provider_factory import get_local_payment_provider


def _currency_payload(data: CurrencyCreate | CurrencyUpdate) -> currency_repository.CurrencyData:
    return data.model_dump(exclude_none=True)  # pyright: ignore[reportReturnType]


async def create_currency_controller(session: AsyncSession, data: CurrencyCreate) -> CurrencyPublic:
    return CurrencyPublic.model_validate(await currency_repository.create(session, _currency_payload(data)))


async def list_currencies_controller(session: AsyncSession, active_only: bool = False) -> list[CurrencyPublic]:
    return [CurrencyPublic.model_validate(item) for item in await currency_repository.get_all(session, active_only)]


async def get_currency_controller(session: AsyncSession, code: str) -> CurrencyPublic:
    currency = await currency_repository.get_by_code(session, code)
    if currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    return CurrencyPublic.model_validate(currency)


async def update_currency_controller(session: AsyncSession, code: str, data: CurrencyUpdate) -> CurrencyPublic:
    currency = await currency_repository.update(session, code, _currency_payload(data))
    if currency is None:
        raise HTTPException(status_code=404, detail="Currency not found")
    return CurrencyPublic.model_validate(currency)


async def set_exchange_rate_controller(session: AsyncSession, base: str, quote: str, rate: float) -> ExchangeRatePublic:
    return await exchange_rate_service.set_manual_rate(session, base, quote, rate)


async def get_exchange_rates_controller(session: AsyncSession, base: str) -> list[ExchangeRatePublic]:
    return [ExchangeRatePublic.model_validate(item) for item in await exchange_rate_repository.get_all_for_base(session, base)]


async def sync_exchange_rates_controller(session: AsyncSession, base: str = "USD") -> dict[str, float]:
    return await exchange_rate_service.sync_rates(session, base)


def get_tax_controller(jurisdiction: str) -> dict[str, float | str]:
    jurisdiction_code = jurisdiction.upper()
    tax_rates = tax_service.get_supported_jurisdictions()
    return {"jurisdiction": jurisdiction_code, "tax_rate": tax_rates.get(jurisdiction_code, 0.0)}


def list_tax_controller() -> dict[str, float]:
    return tax_service.get_supported_jurisdictions()


async def list_wallets_controller(session: AsyncSession, account_id: UUID) -> list[WalletPublic]:
    return await wallet_service.list_wallets(session, account_id)


async def wallet_balance_controller(session: AsyncSession, account_id: UUID, currency: str) -> WalletPublic:
    return await wallet_service.get_balance(session, account_id, currency)


async def credit_wallet_controller(session: AsyncSession, account_id: UUID, currency: str, amount_nano: int, reference: str, idempotency_key: str) -> WalletPublic:
    return await wallet_service.credit_wallet(session, account_id, currency, amount_nano, reference, idempotency_key)


async def convert_wallet_controller(session: AsyncSession, account_id: UUID, from_currency: str, to_currency: str, amount_nano: int, idempotency_key: str) -> ConvertResponse:
    return await wallet_service.convert_wallets(session, account_id, from_currency, to_currency, amount_nano, idempotency_key)


async def initialize_payment_controller(provider: str, amount: int, currency: str, email: str, reference: str, callback_url: str, **kwargs: object) -> dict[str, object]:
    return await get_local_payment_provider(provider).initialize_payment(amount, currency, email, reference, callback_url, **kwargs)


async def verify_payment_controller(provider: str, reference: str) -> dict[str, object]:
    return await get_local_payment_provider(provider).verify_payment(reference)
