from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.ledger import CreditRequest, DebitRequest, LedgerBalancePublic, LedgerEntryPublic, TransferRequest
from swx_core.services import ledger_service


async def credit_controller(session: AsyncSession, request: CreditRequest) -> LedgerEntryPublic:
    return await ledger_service.credit(session, request)


async def debit_controller(session: AsyncSession, request: DebitRequest) -> LedgerEntryPublic:
    return await ledger_service.debit(session, request)


async def refund_controller(session: AsyncSession, account_id: UUID, original_entry_id: UUID, idempotency_key: str) -> LedgerEntryPublic:
    return await ledger_service.refund(session, account_id, original_entry_id, idempotency_key)


async def transfer_controller(session: AsyncSession, request: TransferRequest) -> tuple[LedgerEntryPublic, LedgerEntryPublic]:
    return await ledger_service.transfer(session, request)


async def get_balance_controller(session: AsyncSession, account_id: UUID) -> LedgerBalancePublic:
    return await ledger_service.get_balance(session, account_id)


async def get_entry_history_controller(session: AsyncSession, account_id: UUID, skip: int, limit: int) -> list[LedgerEntryPublic]:
    return await ledger_service.get_entry_history(session, account_id, skip, limit)


async def reconcile_controller(session: AsyncSession, account_id: UUID) -> dict[str, int | bool]:
    return await ledger_service.reconcile(session, account_id)
