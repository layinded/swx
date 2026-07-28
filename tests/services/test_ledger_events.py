import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from swx_core.events import event_bus
from swx_core.models.ledger import CreditRequest, DebitRequest, EntryType, LedgerEntry, ReferenceType, TransferRequest
from swx_core.models.ledger import utc_now_naive


def entry(account_id: UUID, amount: int, balance_after: int, entry_type: str, currency: str = "USD", reference_id: str | None = None, key: str | None = None):
    return LedgerEntry(id=uuid.uuid4(), account_id=account_id, amount=amount, balance_after=balance_after, entry_type=entry_type, currency=currency, reference_type=ReferenceType.ADJUSTMENT.value, reference_id=reference_id, idempotency_key=key, description="desc", metadata_={}, created_at=utc_now_naive(), created_by=None)


class TestLedgerEvents:
    async def test_credit_and_debit_emit_events(self):
        from swx_core.services import ledger_service

        session = AsyncMock()
        account_id = uuid.uuid4()
        with patch("swx_core.services.ledger_service.ledger_repository") as mock_repo:
            mock_repo.get_idempotency_record = AsyncMock(return_value=None)
            mock_repo.get_balance = AsyncMock(return_value=SimpleNamespace(balance=100, currency="USD"))
            mock_repo.create_entry = AsyncMock(side_effect=[entry(account_id, 50, 150, EntryType.CREDIT.value), entry(account_id, 25, 75, EntryType.DEBIT.value)])
            mock_repo.upsert_balance = AsyncMock()
            mock_repo.create_idempotency_record = AsyncMock()
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                credited = await ledger_service.credit(session, CreditRequest(account_id=account_id, amount=50, reference_type="topup", reference_id="r1", idempotency_key="c1"))
                debited = await ledger_service.debit(session, DebitRequest(account_id=account_id, amount=25, reference_type="usage", reference_id="r2", idempotency_key="d1"))

        assert credited.balance_after == 150 and debited.balance_after == 75
        assert [call.args[0] for call in mock_dispatch.call_args_list] == ["ledger.credit", "ledger.debit"]

    async def test_refund_emits_event_and_idempotency_returns_existing_entry(self):
        from swx_core.services import ledger_service

        session = AsyncMock()
        account_id = uuid.uuid4()
        debit_entry = entry(account_id, 20, 80, EntryType.DEBIT.value)
        refund_entry = entry(account_id, 20, 100, EntryType.REFUND.value)
        refund_entry_id = refund_entry.id
        debit_entry_id = debit_entry.id
        record = SimpleNamespace(entry_id=refund_entry_id)

        with patch("swx_core.services.ledger_service.ledger_repository") as mock_repo:
            mock_repo.get_idempotency_record = AsyncMock(side_effect=[None, record])
            mock_repo.get_entry_by_id = AsyncMock(side_effect=[debit_entry, refund_entry, refund_entry])
            mock_repo.get_balance = AsyncMock(return_value=SimpleNamespace(balance=80, currency="USD"))
            mock_repo.create_entry = AsyncMock(return_value=refund_entry)
            mock_repo.upsert_balance = AsyncMock()
            mock_repo.create_idempotency_record = AsyncMock()
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                created = await ledger_service.refund(session, account_id, debit_entry_id, "refund-key")
                existing = await ledger_service.refund(session, account_id, debit_entry_id, "refund-key")

        assert created.id == existing.id == refund_entry_id
        assert mock_dispatch.call_args.args[0] == "ledger.refund"
        assert mock_dispatch.await_count == 1

    async def test_transfer_emits_unified_event(self):
        from swx_core.services import ledger_service

        session = AsyncMock()
        request = TransferRequest(from_account_id=uuid.uuid4(), to_account_id=uuid.uuid4(), amount=40, currency="USD", idempotency_key="tx1", description="move")
        debit_entry = entry(request.from_account_id, 40, 60, EntryType.DEBIT.value, key="tx1")
        credit_entry = entry(request.to_account_id, 40, 140, EntryType.CREDIT.value, reference_id=str(debit_entry.id), key="tx1")

        with patch("swx_core.services.ledger_service.ledger_repository") as mock_repo:
            mock_repo.get_idempotency_record = AsyncMock(return_value=None)
            mock_repo.get_balance = AsyncMock(side_effect=[SimpleNamespace(balance=100, currency="USD"), SimpleNamespace(balance=100, currency="USD")])
            mock_repo.create_entry = AsyncMock(side_effect=[debit_entry, credit_entry])
            mock_repo.upsert_balance = AsyncMock()
            mock_repo.create_idempotency_record = AsyncMock()
            with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                debit_public, credit_public = await ledger_service.transfer(session, request)

        assert debit_public.id == debit_entry.id and credit_public.id == credit_entry.id
        assert [call.args[0] for call in mock_dispatch.call_args_list] == ["ledger.debit", "ledger.credit", "ledger.transfer"]

    async def test_duplicate_idempotency_key_returns_existing_credit_entry(self):
        from swx_core.services import ledger_service

        session = AsyncMock()
        existing = entry(uuid.uuid4(), 30, 130, EntryType.CREDIT.value, key="dup")
        with patch("swx_core.services.ledger_service.ledger_repository") as mock_repo:
            mock_repo.get_idempotency_record = AsyncMock(return_value=SimpleNamespace(entry_id=existing.id))
            mock_repo.get_entry_by_id = AsyncMock(return_value=existing)
            result = await ledger_service.credit(session, CreditRequest(account_id=existing.account_id, amount=30, idempotency_key="dup"))

        assert result.id == existing.id

    async def test_insufficient_balance_raises_http_exception(self):
        from swx_core.services import ledger_service

        session = AsyncMock()
        with patch("swx_core.services.ledger_service.ledger_repository") as mock_repo:
            mock_repo.get_idempotency_record = AsyncMock(return_value=None)
            mock_repo.get_balance = AsyncMock(return_value=SimpleNamespace(balance=10, currency="USD"))
            with pytest.raises(HTTPException, match="Insufficient ledger balance"):
                _ = await ledger_service.debit(session, DebitRequest(account_id=uuid.uuid4(), amount=50, idempotency_key="low"))
