from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.events import event_bus
from swx_core.models.billing import BillingAccountType
from swx_core.models.currency import ConvertResponse, Wallet, WalletPublic
from swx_core.models.ledger import CreditRequest, DebitRequest
from swx_core.repositories import billing_repository, wallet_repository
from swx_core.services import ledger_service
from swx_core.services.audit_logger import ActorType, AuditOutcome, get_audit_logger
from swx_core.services.billing import exchange_rate_service
from swx_core.services.billing.subscription_service import SubscriptionService


def _public(wallet: Wallet) -> WalletPublic:
    return WalletPublic.model_validate(wallet)


async def _audit(
    session: AsyncSession,
    action: str,
    actor_type: ActorType | str,
    actor_id: str | None,
    resource_type: str,
    resource_id: str,
    context: dict[str, object],
) -> None:
    await get_audit_logger(session).log_event(
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=AuditOutcome.SUCCESS,
        context=context,
    )


async def _dispatch(event_name: str, payload: dict[str, object]) -> None:
    await event_bus.dispatch(event_name, payload=payload)


async def _wallet_entity(session: AsyncSession, account_id: UUID, currency: str) -> Wallet:
    wallet = await wallet_repository.get_by_account_currency(session, account_id, currency)
    if wallet is not None:
        return wallet
    return await wallet_repository.create(session, {"account_id": account_id, "currency": currency.upper(), "balance": 0, "is_active": True, "extra_data": {}})


async def get_or_create_wallet(session: AsyncSession, account_id: UUID, currency: str) -> WalletPublic:
    return _public(await _wallet_entity(session, account_id, currency))


async def get_balance(session: AsyncSession, account_id: UUID, currency: str) -> WalletPublic:
    return await get_or_create_wallet(session, account_id, currency)


async def list_wallets(session: AsyncSession, account_id: UUID) -> list[WalletPublic]:
    return [_public(wallet) for wallet in await wallet_repository.get_wallets_for_account(session, account_id)]


async def _credit_wallet_atomic(session: AsyncSession, account_id: UUID, currency: str, amount_nano: int, reference: str, idempotency_key: str) -> Wallet:
    """Credit wallet + ledger in a single transaction — caller controls commit."""
    wallet = await _wallet_entity(session, account_id, currency)
    entry = await ledger_service.credit(session, CreditRequest(
        account_id=wallet.id, amount=amount_nano, currency=wallet.currency,
        reference_type="wallet", reference_id=reference, idempotency_key=idempotency_key,
        description=f"Wallet credit {wallet.currency}",
    ), auto_commit=False)
    updated = await wallet_repository.update_balance_no_commit(session, wallet.id, entry.balance_after)
    if updated is None:
        raise HTTPException(status_code=500, detail="Wallet balance update failed")
    return updated


async def _debit_wallet_atomic(session: AsyncSession, account_id: UUID, currency: str, amount_nano: int, reference: str, idempotency_key: str) -> Wallet:
    """Debit wallet + ledger in a single transaction — caller controls commit."""
    wallet = await wallet_repository.get_by_account_currency_for_update(session, account_id, currency)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    if wallet.balance < amount_nano:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")
    entry = await ledger_service.debit(session, DebitRequest(
        account_id=wallet.id, amount=amount_nano, currency=wallet.currency,
        reference_type="wallet", reference_id=reference, idempotency_key=idempotency_key,
        description=f"Wallet debit {wallet.currency}",
    ), auto_commit=False)
    updated = await wallet_repository.update_balance_no_commit(session, wallet.id, entry.balance_after)
    if updated is None:
        raise HTTPException(status_code=500, detail="Wallet balance update failed")
    return updated


async def credit_wallet(session: AsyncSession, account_id: UUID, currency: str, amount_nano: int, reference: str, idempotency_key: str, *, actor_type: ActorType | str = ActorType.SYSTEM, actor_id: str | None = None) -> WalletPublic:
    try:
        wallet = await _credit_wallet_atomic(session, account_id, currency, amount_nano, reference, idempotency_key)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await _dispatch("wallet.credit", {"wallet_id": str(wallet.id), "account_id": str(account_id), "currency": wallet.currency, "amount": amount_nano, "reference": reference})
    await _audit(session, "wallet.credit", actor_type, actor_id, "wallet", str(wallet.id), {"account_id": str(account_id), "currency": wallet.currency, "amount": amount_nano, "reference": reference})
    return _public(wallet)


async def credit_wallet_internal(session: AsyncSession, account_id: UUID, currency: str, amount_nano: int, *, actor_id: str | None = None) -> WalletPublic:
    """Credit a wallet with auto-generated reference and idempotency key.

    Convenience for internal callers that don't need to specify
    reference/idempotency_key (e.g. referral bonuses, grace period credits).
    """
    key = uuid4().hex
    return await credit_wallet(session, account_id, currency, amount_nano, f"internal-{key}", f"internal-{key}", actor_type=ActorType.SYSTEM, actor_id=actor_id)


async def debit_wallet(session: AsyncSession, account_id: UUID, currency: str, amount_nano: int, reference: str, idempotency_key: str, *, actor_type: ActorType | str = ActorType.SYSTEM, actor_id: str | None = None) -> WalletPublic:
    try:
        wallet = await _debit_wallet_atomic(session, account_id, currency, amount_nano, reference, idempotency_key)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await _dispatch("wallet.debit", {"wallet_id": str(wallet.id), "account_id": str(account_id), "currency": wallet.currency, "amount": amount_nano, "reference": reference})
    await _audit(session, "wallet.debit", actor_type, actor_id, "wallet", str(wallet.id), {"account_id": str(account_id), "currency": wallet.currency, "amount": amount_nano, "reference": reference})
    return _public(wallet)


async def transfer(session: AsyncSession, account_id: UUID, from_currency: str, to_currency: str, amount_nano: int, idempotency_key: str, *, actor_type: ActorType | str = ActorType.SYSTEM, actor_id: str | None = None) -> tuple[WalletPublic, WalletPublic]:
    converted_amount = await exchange_rate_service.convert(session, amount_nano, from_currency, to_currency)
    try:
        from_wallet = await _debit_wallet_atomic(session, account_id, from_currency, amount_nano, f"convert:{to_currency}", f"{idempotency_key}:debit")
        to_wallet = await _credit_wallet_atomic(session, account_id, to_currency, converted_amount, f"convert:{from_currency}", f"{idempotency_key}:credit")
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await _dispatch("wallet.transfer", {"account_id": str(account_id), "from_currency": from_currency.upper(), "to_currency": to_currency.upper(), "amount": amount_nano, "converted_amount": converted_amount})
    await _audit(session, "wallet.transfer", actor_type, actor_id, "wallet", str(from_wallet.id), {"account_id": str(account_id), "from_currency": from_currency.upper(), "to_currency": to_currency.upper(), "amount": amount_nano, "converted_amount": converted_amount})
    return _public(from_wallet), _public(to_wallet)


async def convert_wallets(session: AsyncSession, account_id: UUID, from_currency: str, to_currency: str, amount_nano: int, idempotency_key: str, *, actor_type: ActorType | str = ActorType.SYSTEM, actor_id: str | None = None) -> ConvertResponse:
    rate = await exchange_rate_service.get_rate(session, from_currency, to_currency)
    converted_amount = round(amount_nano * rate)
    from_wallet, to_wallet = await transfer(session, account_id, from_currency, to_currency, amount_nano, idempotency_key, actor_type=actor_type, actor_id=actor_id)
    return ConvertResponse(from_wallet=from_wallet, to_wallet=to_wallet, converted_amount_nano=converted_amount, rate=rate)


async def resolve_wallet_for_charge(
    session: AsyncSession, user_id: UUID, org_id: UUID | None = None, currency: str | None = None
) -> WalletPublic:
    """Resolve which wallet to charge based on org/personal priority.

    - org_id provided → charge org wallet
    - no org_id → charge personal wallet
    - never cross-charge
    - empty wallet → raise HTTPException 402
    """
    charge_currency = currency or settings.DEFAULT_BASE_CURRENCY
    if org_id is not None:
        account = await billing_repository.get_user_billing_account(session, org_id)
        account_type = BillingAccountType.ORGANIZATION
    else:
        account = await billing_repository.get_user_billing_account(session, user_id)
        account_type = BillingAccountType.USER

    if account is None:
        sub_service = SubscriptionService(session)
        account = await sub_service.get_or_create_account(user_id, account_type)

    wallet = await wallet_repository.get_by_account_currency(session, account.id, charge_currency)
    if wallet is None or wallet.balance <= 0:
        raise HTTPException(status_code=402, detail=f"Insufficient balance in {charge_currency} wallet")

    return _public(wallet)