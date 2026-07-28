from uuid import UUID

from fastapi import APIRouter, Depends

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import ledger_controller
from swx_core.database.db import SessionDep
from swx_core.models.ledger import CreditRequest, DebitRequest, LedgerBalancePublic, LedgerEntryPublic, TransferRequest

router = APIRouter(prefix="/admin/ledger", tags=["admin-ledger"], dependencies=[Depends(get_current_admin_user)])


@router.post("/credit", response_model=LedgerEntryPublic, status_code=201)
async def credit(session: SessionDep, request: CreditRequest) -> LedgerEntryPublic:
    return await ledger_controller.credit_controller(session, request)


@router.post("/debit", response_model=LedgerEntryPublic, status_code=201)
async def debit(session: SessionDep, request: DebitRequest) -> LedgerEntryPublic:
    return await ledger_controller.debit_controller(session, request)


@router.post("/refund", response_model=LedgerEntryPublic, status_code=201)
async def refund(session: SessionDep, account_id: UUID, original_entry_id: UUID, idempotency_key: str) -> LedgerEntryPublic:
    return await ledger_controller.refund_controller(session, account_id, original_entry_id, idempotency_key)


@router.post("/transfer", response_model=tuple[LedgerEntryPublic, LedgerEntryPublic], status_code=201)
async def transfer(session: SessionDep, request: TransferRequest) -> tuple[LedgerEntryPublic, LedgerEntryPublic]:
    return await ledger_controller.transfer_controller(session, request)


@router.get("/{account_id}/balance", response_model=LedgerBalancePublic)
async def get_balance(session: SessionDep, account_id: UUID) -> LedgerBalancePublic:
    return await ledger_controller.get_balance_controller(session, account_id)


@router.get("/{account_id}/entries", response_model=list[LedgerEntryPublic])
async def get_entries(session: SessionDep, account_id: UUID, skip: int = 0, limit: int = 100) -> list[LedgerEntryPublic]:
    return await ledger_controller.get_entry_history_controller(session, account_id, skip, limit)


@router.get("/{account_id}/reconcile", response_model=dict[str, int | bool])
async def reconcile(session: SessionDep, account_id: UUID) -> dict[str, int | bool]:
    return await ledger_controller.reconcile_controller(session, account_id)
