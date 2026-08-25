from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.database.session_helpers import with_read_session
from swx_core.models.currency import (
    ConvertResponse,
    CurrencyCreate,
    CurrencyPublic,
    CurrencyUpdate,
    ExchangeRatePublic,
    WalletPublic,
)
from swx_core.models.ledger import LedgerEntryPublic
from swx_core.services import ledger_service
from swx_core.services.billing import (
    billing_service,
    currency_service,
    exchange_rate_service,
    tax_service,
    wallet_service,
)
from swx_core.services.billing.provider_factory import get_local_payment_provider
from swx_core.utils.currency import major_to_provider_amount
from swx_core.utils.errors import NotFoundError


async def create_currency_controller(session: AsyncSession, data: CurrencyCreate) -> CurrencyPublic:
    return CurrencyPublic.model_validate(await currency_service.create_currency(session, data))


async def list_currencies_controller(session: AsyncSession, active_only: bool = False) -> list[CurrencyPublic]:
    return [CurrencyPublic.model_validate(item) for item in await currency_service.list_currencies(session, active_only)]


async def get_currency_controller(session: AsyncSession, code: str) -> CurrencyPublic:
    currency = await currency_service.get_currency_by_code(session, code)
    if currency is None:
        raise NotFoundError("Currency", code)
    return CurrencyPublic.model_validate(currency)


async def update_currency_controller(session: AsyncSession, code: str, data: CurrencyUpdate) -> CurrencyPublic:
    currency = await currency_service.update_currency(session, code, data)
    if currency is None:
        raise NotFoundError("Currency", code)
    return CurrencyPublic.model_validate(currency)


async def set_exchange_rate_controller(session: AsyncSession, base: str, quote: str, rate: float) -> ExchangeRatePublic:
    return await exchange_rate_service.set_manual_rate(session, base, quote, rate)


async def get_exchange_rates_controller(session: AsyncSession, base: str) -> list[ExchangeRatePublic]:
    return [ExchangeRatePublic.model_validate(item) for item in await exchange_rate_service.get_all_for_base(session, base)]


async def sync_exchange_rates_controller(session: AsyncSession, base: str | None = None) -> dict[str, float]:
    return await exchange_rate_service.sync_rates(session, base or settings.DEFAULT_BASE_CURRENCY)


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


async def debit_wallet_controller(session: AsyncSession, account_id: UUID, currency: str, amount_nano: int, reference: str, idempotency_key: str) -> WalletPublic:
    return await wallet_service.debit_wallet(session, account_id, currency, amount_nano, reference, idempotency_key)


async def transfer_wallet_controller(session: AsyncSession, account_id: UUID, from_currency: str, to_currency: str, amount_nano: int, idempotency_key: str) -> tuple[WalletPublic, WalletPublic]:
    return await wallet_service.transfer(session, account_id, from_currency, to_currency, amount_nano, idempotency_key)


async def convert_wallet_controller(session: AsyncSession, account_id: UUID, from_currency: str, to_currency: str, amount_nano: int, idempotency_key: str) -> ConvertResponse:
    return await wallet_service.convert_wallets(session, account_id, from_currency, to_currency, amount_nano, idempotency_key)


async def initialize_payment_controller(provider: str, amount: int, currency: str, email: str, reference: str, callback_url: str, **kwargs: object) -> dict[str, object]:
    return await get_local_payment_provider(provider).initialize_payment(amount, currency, email, reference, callback_url, **kwargs)


async def verify_payment_controller(provider: str, reference: str) -> dict[str, object]:
    return await get_local_payment_provider(provider).verify_payment(reference)


async def list_public_plans_controller() -> list[dict[str, object]]:
    async with with_read_session() as session:
        plans = await billing_service.list_public_plans(session)
    return [
        {
            "key": plan.key,
            "name": plan.name,
            "description": plan.description,
            "amount": plan.amount,
            "currency": plan.currency,
            "billing_interval": plan.billing_interval.value,
        }
        for plan in plans
    ]


async def initialize_payment_for_plan_controller(
    plan_key: str, provider: str, callback_url: str, email: str, currency: str | None = None
) -> dict[str, object]:
    async with with_read_session() as session:
        plan = await billing_service.get_plan_by_key(session, plan_key)
        if plan is None:
            raise NotFoundError("Plan", plan_key)
        if plan.amount is None:
            raise NotFoundError("Plan price", plan_key)
        plan_currency = currency or plan.currency or settings.DEFAULT_BASE_CURRENCY
        plan_amount = plan.amount

    return await _call_provider_with_amount(
        "plan", plan_key, plan_amount, plan_currency, provider, callback_url, email
    )


async def list_credit_packs_controller() -> list[dict[str, object]]:
    async with with_read_session() as session:
        packs = await billing_service.list_public_credit_packs(session)
    return [
        {
            "key": pack.key,
            "name": pack.name,
            "description": pack.description,
            "tokens": pack.tokens,
            "amount": pack.amount,
            "currency": pack.currency,
        }
        for pack in packs
    ]


async def initialize_payment_for_pack_controller(
    pack_key: str, provider: str, callback_url: str, email: str
) -> dict[str, object]:
    async with with_read_session() as session:
        pack = await billing_service.get_credit_pack_by_key(session, pack_key)
        if pack is None:
            raise NotFoundError("Credit pack", pack_key)
        pack_amount = pack.amount
        pack_currency = pack.currency

    return await _call_provider_with_amount(
        "pack", pack_key, pack_amount, pack_currency, provider, callback_url, email
    )


async def _call_provider_with_amount(
    prefix: str, item_key: str, item_amount: int, item_currency: str, provider: str, callback_url: str, email: str
) -> dict[str, object]:
    provider_amount = major_to_provider_amount(float(item_amount), item_currency, provider)
    reference = f"{prefix}-{item_key}-{uuid4().hex}"
    return await get_local_payment_provider(provider).initialize_payment(
        provider_amount, item_currency, email, reference, callback_url
    )


async def list_transactions_controller(
    session: AsyncSession,
    user_id: UUID,
    entry_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[LedgerEntryPublic]:
    account = await billing_service.get_user_billing_account(session, user_id)
    if account is None:
        return []
    return await ledger_service.get_filtered_entry_history(
        session,
        account.id,
        entry_type=entry_type,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
