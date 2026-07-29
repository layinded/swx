from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.events import event_bus
from swx_core.models.ledger import (
    CreditRequest,
    DebitRequest,
    EntryType,
    IdempotencyRecord,
    LedgerBalancePublic,
    LedgerEntry,
    LedgerEntryPublic,
    ReferenceType,
    TransferRequest,
)
from swx_core.repositories import ledger_repository
from swx_core.utils.time import utc_now


def _entry_public(entry: LedgerEntry) -> LedgerEntryPublic:
    return LedgerEntryPublic(
        id=entry.id,
        account_id=entry.account_id,
        entry_type=entry.entry_type,
        amount=entry.amount,
        currency=entry.currency,
        reference_type=entry.reference_type,
        reference_id=entry.reference_id,
        idempotency_key=entry.idempotency_key,
        description=entry.description,
        entry_metadata=entry.metadata_,
        balance_after=entry.balance_after,
        created_at=entry.created_at,
        created_by=entry.created_by,
    )


def _balance_public(balance_id: UUID, account_id: UUID, currency: str, balance: int, last_entry_id: UUID | None, updated_at) -> LedgerBalancePublic:
    return LedgerBalancePublic(id=balance_id, account_id=account_id, currency=currency, balance=balance, last_entry_id=last_entry_id, updated_at=updated_at)


async def _existing_entry(session: AsyncSession, record: IdempotencyRecord | None) -> LedgerEntry | None:
    if not record or not record.entry_id:
        return None
    return await ledger_repository.get_entry_by_id(session, record.entry_id)


async def _current_balance(session: AsyncSession, account_id: UUID) -> tuple[int, str]:
    balance = await ledger_repository.get_balance(session, account_id)
    if balance is not None:
        return balance.balance, balance.currency
    latest = await ledger_repository.get_latest_entry(session, account_id)
    if latest is not None:
        return latest.balance_after, latest.currency
    return 0, "USD"


async def credit(session: AsyncSession, request: CreditRequest) -> LedgerEntryPublic:
    idempotency_record = await ledger_repository.get_idempotency_record(session, request.idempotency_key) if request.idempotency_key else None
    existing_entry = await _existing_entry(session, idempotency_record)
    if request.idempotency_key and existing_entry is not None:
        return _entry_public(existing_entry)
    current_balance, currency = await _current_balance(session, request.account_id)
    entry_currency = request.currency or currency
    try:
        entry = await ledger_repository.create_entry(session, {"account_id": request.account_id, "entry_type": EntryType.CREDIT.value, "amount": request.amount, "currency": entry_currency, "reference_type": request.reference_type, "reference_id": request.reference_id, "idempotency_key": request.idempotency_key, "description": request.description, "balance_after": current_balance + request.amount, "metadata_": {}})
        await ledger_repository.upsert_balance(session, request.account_id, entry.balance_after, entry.id, entry.currency)
        if request.idempotency_key:
            await ledger_repository.create_idempotency_record(session, {"key": request.idempotency_key, "account_id": request.account_id, "entry_id": entry.id, "status": "completed"})
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await event_bus.dispatch("ledger.credit", payload={"account_id": str(request.account_id), "entry_id": str(entry.id), "amount": request.amount})
    return _entry_public(entry)


async def debit(session: AsyncSession, request: DebitRequest) -> LedgerEntryPublic:
    idempotency_record = await ledger_repository.get_idempotency_record(session, request.idempotency_key) if request.idempotency_key else None
    existing_entry = await _existing_entry(session, idempotency_record)
    if request.idempotency_key and existing_entry is not None:
        return _entry_public(existing_entry)
    current_balance, currency = await _current_balance(session, request.account_id)
    if not settings.LEDGER_ALLOW_NEGATIVE_BALANCE and current_balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient ledger balance")
    entry_currency = request.currency or currency
    try:
        entry = await ledger_repository.create_entry(session, {"account_id": request.account_id, "entry_type": EntryType.DEBIT.value, "amount": request.amount, "currency": entry_currency, "reference_type": request.reference_type, "reference_id": request.reference_id, "idempotency_key": request.idempotency_key, "description": request.description, "balance_after": current_balance - request.amount, "metadata_": {}})
        await ledger_repository.upsert_balance(session, request.account_id, entry.balance_after, entry.id, entry.currency)
        if request.idempotency_key:
            await ledger_repository.create_idempotency_record(session, {"key": request.idempotency_key, "account_id": request.account_id, "entry_id": entry.id, "status": "completed"})
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await event_bus.dispatch("ledger.debit", payload={"account_id": str(request.account_id), "entry_id": str(entry.id), "amount": request.amount})
    return _entry_public(entry)


async def refund(session: AsyncSession, account_id: UUID, original_entry_id: UUID, idempotency_key: str) -> LedgerEntryPublic:
    idempotency_record = await ledger_repository.get_idempotency_record(session, idempotency_key)
    existing_entry = await _existing_entry(session, idempotency_record)
    if existing_entry is not None:
        return _entry_public(existing_entry)
    original_entry = await ledger_repository.get_entry_by_id(session, original_entry_id)
    if not original_entry or original_entry.account_id != account_id or original_entry.entry_type != EntryType.DEBIT.value:
        raise HTTPException(status_code=404, detail="Original debit entry not found")
    current_balance, _ = await _current_balance(session, account_id)
    try:
        entry = await ledger_repository.create_entry(session, {"account_id": account_id, "entry_type": EntryType.REFUND.value, "amount": original_entry.amount, "currency": original_entry.currency, "reference_type": ReferenceType.REFUND.value, "reference_id": str(original_entry_id), "idempotency_key": idempotency_key, "description": f"Refund for entry {original_entry_id}", "balance_after": current_balance + original_entry.amount, "metadata_": {}})
        await ledger_repository.upsert_balance(session, account_id, entry.balance_after, entry.id, entry.currency)
        await ledger_repository.create_idempotency_record(session, {"key": idempotency_key, "account_id": account_id, "entry_id": entry.id, "status": "completed"})
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await event_bus.dispatch("ledger.refund", payload={"account_id": str(account_id), "entry_id": str(entry.id), "original_entry_id": str(original_entry_id)})
    return _entry_public(entry)


async def transfer(session: AsyncSession, request: TransferRequest) -> tuple[LedgerEntryPublic, LedgerEntryPublic]:
    record = await ledger_repository.get_idempotency_record(session, request.idempotency_key)
    if record and record.entry_id:
        debit_entry = await ledger_repository.get_entry_by_id(session, record.entry_id)
        if debit_entry is None:
            raise HTTPException(status_code=409, detail="Transfer idempotency record is invalid")
        credit_entries = await ledger_repository.get_entries_by_reference(session, request.to_account_id, ReferenceType.ADJUSTMENT.value, str(debit_entry.id))
        if not credit_entries:
            raise HTTPException(status_code=409, detail="Transfer credit leg not found")
        return _entry_public(debit_entry), _entry_public(credit_entries[0])
    from_balance, _ = await _current_balance(session, request.from_account_id)
    to_balance, _ = await _current_balance(session, request.to_account_id)
    if not settings.LEDGER_ALLOW_NEGATIVE_BALANCE and from_balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient ledger balance")
    try:
        debit_entry = await ledger_repository.create_entry(session, {"account_id": request.from_account_id, "entry_type": EntryType.DEBIT.value, "amount": request.amount, "currency": request.currency, "reference_type": ReferenceType.ADJUSTMENT.value, "reference_id": request.idempotency_key, "idempotency_key": request.idempotency_key, "description": request.description, "balance_after": from_balance - request.amount, "metadata_": {"transfer_to_account_id": str(request.to_account_id)}})
        credit_entry = await ledger_repository.create_entry(session, {"account_id": request.to_account_id, "entry_type": EntryType.CREDIT.value, "amount": request.amount, "currency": request.currency, "reference_type": ReferenceType.ADJUSTMENT.value, "reference_id": str(debit_entry.id), "idempotency_key": request.idempotency_key, "description": request.description, "balance_after": to_balance + request.amount, "metadata_": {"transfer_from_account_id": str(request.from_account_id)}})
        await ledger_repository.upsert_balance(session, request.from_account_id, debit_entry.balance_after, debit_entry.id, request.currency)
        await ledger_repository.upsert_balance(session, request.to_account_id, credit_entry.balance_after, credit_entry.id, request.currency)
        await ledger_repository.create_idempotency_record(session, {"key": request.idempotency_key, "account_id": request.from_account_id, "entry_id": debit_entry.id, "status": "completed"})
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await event_bus.dispatch("ledger.debit", payload={"account_id": str(request.from_account_id), "entry_id": str(debit_entry.id), "amount": request.amount})
    await event_bus.dispatch("ledger.credit", payload={"account_id": str(request.to_account_id), "entry_id": str(credit_entry.id), "amount": request.amount})
    await event_bus.dispatch("ledger.transfer", payload={"from_account_id": str(request.from_account_id), "to_account_id": str(request.to_account_id), "debit_entry_id": str(debit_entry.id), "credit_entry_id": str(credit_entry.id), "amount": request.amount})
    return _entry_public(debit_entry), _entry_public(credit_entry)


async def get_balance(session: AsyncSession, account_id: UUID) -> LedgerBalancePublic:
    balance = await ledger_repository.get_balance(session, account_id)
    if balance is not None:
        return _balance_public(balance.id, balance.account_id, balance.currency, balance.balance, balance.last_entry_id, balance.updated_at)
    latest = await ledger_repository.get_latest_entry(session, account_id)
    if latest is not None:
        cached = await ledger_repository.upsert_balance(session, account_id, latest.balance_after, latest.id, latest.currency)
        await session.commit()
        return _balance_public(cached.id, cached.account_id, cached.currency, cached.balance, cached.last_entry_id, cached.updated_at)
    return LedgerBalancePublic(id=UUID(int=0), account_id=account_id, currency="USD", balance=0, last_entry_id=None, updated_at=utc_now())


async def get_entry_history(session: AsyncSession, account_id: UUID, skip: int, limit: int) -> list[LedgerEntryPublic]:
    return [_entry_public(entry) for entry in await ledger_repository.get_entries_by_account(session, account_id, skip, limit)]


async def reconcile(session: AsyncSession, account_id: UUID) -> dict[str, int | bool]:
    cached = await ledger_repository.get_balance(session, account_id)
    credits = await ledger_repository.sum_entries(session, account_id, EntryType.CREDIT.value)
    debits = await ledger_repository.sum_entries(session, account_id, EntryType.DEBIT.value)
    refunds = await ledger_repository.sum_entries(session, account_id, EntryType.REFUND.value)
    adjustments = await ledger_repository.sum_entries(session, account_id, EntryType.ADJUSTMENT.value)
    computed = credits + refunds + adjustments - debits
    cached_balance = cached.balance if cached is not None else 0
    return {"cached_balance": cached_balance, "computed_balance": computed, "matches": cached_balance == computed}
