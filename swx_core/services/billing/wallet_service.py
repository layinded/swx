from uuid import UUID
from collections.abc import Awaitable
from typing import Protocol, cast

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events import event_bus
from swx_core.models.currency import ConvertResponse, WalletPublic
from swx_core.models.currency import Wallet
from swx_core.models.ledger import CreditRequest, DebitRequest
from swx_core.repositories import wallet_repository
from swx_core.services import ledger_service
from swx_core.services.billing import exchange_rate_service


class _EventDispatcher(Protocol):
    def dispatch(self, event_name: str, payload: dict[str, object] | None = None, **kwargs: object) -> Awaitable[object]:
        ...


def _public(wallet: Wallet) -> WalletPublic:
    return WalletPublic.model_validate(wallet)


async def _wallet_entity(session: AsyncSession, account_id: UUID, currency: str) -> Wallet:
    wallet = await wallet_repository.get_by_account_currency(session, account_id, currency)
    if wallet is not None:
        return wallet
    return await wallet_repository.create(session, {"account_id": account_id, "currency": currency.upper(), "balance": 0, "is_active": True, "extra_data": {}})


async def _dispatch_event(event_name: str, payload: dict[str, object]) -> None:
    _ = await cast(_EventDispatcher, cast(object, event_bus)).dispatch(event_name, payload=payload)


async def get_or_create_wallet(session: AsyncSession, account_id: UUID, currency: str) -> WalletPublic:
    return _public(await _wallet_entity(session, account_id, currency))


async def get_balance(session: AsyncSession, account_id: UUID, currency: str) -> WalletPublic:
    return await get_or_create_wallet(session, account_id, currency)


async def list_wallets(session: AsyncSession, account_id: UUID) -> list[WalletPublic]:
    return [_public(wallet) for wallet in await wallet_repository.get_wallets_for_account(session, account_id)]


async def credit_wallet(session: AsyncSession, account_id: UUID, currency: str, amount_nano: int, reference: str, idempotency_key: str) -> WalletPublic:
    wallet = await _wallet_entity(session, account_id, currency)
    entry = await ledger_service.credit(session, CreditRequest(account_id=wallet.id, amount=amount_nano, currency=wallet.currency, reference_type="wallet", reference_id=reference, idempotency_key=idempotency_key, description=f"Wallet credit {wallet.currency}"))
    updated = await wallet_repository.update_balance(session, wallet.id, entry.balance_after)
    if updated is None:
        raise HTTPException(status_code=500, detail="Wallet balance update failed")
    await _dispatch_event("wallet.credit", {"wallet_id": str(wallet.id), "account_id": str(account_id), "currency": wallet.currency, "amount": amount_nano, "reference": reference})
    return _public(updated)


async def debit_wallet(session: AsyncSession, account_id: UUID, currency: str, amount_nano: int, reference: str, idempotency_key: str) -> WalletPublic:
    wallet = await wallet_repository.get_by_account_currency(session, account_id, currency)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    if wallet.balance < amount_nano:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")
    entry = await ledger_service.debit(session, DebitRequest(account_id=wallet.id, amount=amount_nano, currency=wallet.currency, reference_type="wallet", reference_id=reference, idempotency_key=idempotency_key, description=f"Wallet debit {wallet.currency}"))
    updated = await wallet_repository.update_balance(session, wallet.id, entry.balance_after)
    if updated is None:
        raise HTTPException(status_code=500, detail="Wallet balance update failed")
    await _dispatch_event("wallet.debit", {"wallet_id": str(wallet.id), "account_id": str(account_id), "currency": wallet.currency, "amount": amount_nano, "reference": reference})
    return _public(updated)


async def transfer(session: AsyncSession, account_id: UUID, from_currency: str, to_currency: str, amount_nano: int, idempotency_key: str) -> tuple[WalletPublic, WalletPublic]:
    converted_amount = await exchange_rate_service.convert(session, amount_nano, from_currency, to_currency)
    from_wallet = await debit_wallet(session, account_id, from_currency, amount_nano, f"convert:{to_currency}", f"{idempotency_key}:debit")
    to_wallet = await credit_wallet(session, account_id, to_currency, converted_amount, f"convert:{from_currency}", f"{idempotency_key}:credit")
    await _dispatch_event("wallet.transfer", {"account_id": str(account_id), "from_currency": from_currency.upper(), "to_currency": to_currency.upper(), "amount": amount_nano, "converted_amount": converted_amount})
    return from_wallet, to_wallet


async def convert_wallets(session: AsyncSession, account_id: UUID, from_currency: str, to_currency: str, amount_nano: int, idempotency_key: str) -> ConvertResponse:
    rate = await exchange_rate_service.get_rate(session, from_currency, to_currency)
    converted_amount = int(round(amount_nano * rate))
    from_wallet, to_wallet = await transfer(session, account_id, from_currency, to_currency, amount_nano, idempotency_key)
    return ConvertResponse(from_wallet=from_wallet, to_wallet=to_wallet, converted_amount_nano=converted_amount, rate=rate)
