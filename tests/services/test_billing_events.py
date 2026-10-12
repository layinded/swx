import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

from swx_core.events import event_bus
from swx_core.models.currency import utc_now_naive
from swx_core.services.billing import tax_service


def wallet(account_id: UUID, currency: str, balance: int):
    return SimpleNamespace(id=uuid.uuid4(), account_id=account_id, currency=currency, balance=balance, is_active=True, extra_data={}, created_at=utc_now_naive(), updated_at=utc_now_naive())


class TestBillingEvents:
    async def test_wallet_credit_debit_and_transfer_emit_events(self):
        from swx_core.services.billing import wallet_service

        session = AsyncMock()
        account_id = uuid.uuid4()
        usd_wallet = wallet(account_id, "USD", 100)
        ngn_wallet = wallet(account_id, "NGN", 0)

        with patch("swx_core.services.billing.wallet_service.wallet_repository") as mock_repo:
            mock_repo.get_by_account_currency = AsyncMock(side_effect=[usd_wallet, usd_wallet, usd_wallet, ngn_wallet])
            mock_repo.create = AsyncMock(return_value=ngn_wallet)
            mock_repo.update_balance = AsyncMock(side_effect=[wallet(account_id, "USD", 150), wallet(account_id, "USD", 110), wallet(account_id, "USD", 90), wallet(account_id, "NGN", 3000)])
            with patch("swx_core.services.billing.wallet_service.ledger_service") as mock_ledger:
                mock_ledger.credit = AsyncMock(side_effect=[SimpleNamespace(balance_after=150), SimpleNamespace(balance_after=3000)])
                mock_ledger.debit = AsyncMock(side_effect=[SimpleNamespace(balance_after=110), SimpleNamespace(balance_after=90)])
                with patch("swx_core.services.billing.wallet_service.exchange_rate_service.convert", new_callable=AsyncMock, return_value=3000):
                    with patch.object(event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                        credited = await wallet_service.credit_wallet(session, account_id, "USD", 50, "topup", "c1")
                        debited = await wallet_service.debit_wallet(session, account_id, "USD", 40, "usage", "d1")
                        from_wallet, to_wallet = await wallet_service.transfer(session, account_id, "USD", "NGN", 20, "t1")

        assert credited.balance == 150 and debited.balance == 110
        assert from_wallet.currency == "USD" and to_wallet.currency == "NGN"
        assert [call.args[0] for call in mock_dispatch.call_args_list] == ["wallet.credit", "wallet.debit", "wallet.debit", "wallet.credit", "wallet.transfer"]

    async def test_exchange_rate_resolution_direct_inverse_and_pivot(self):
        from swx_core.services.billing import exchange_rate_service

        session = AsyncMock()
        with patch("swx_core.services.billing.exchange_rate_service.exchange_rate_repository") as mock_rates:
            with patch("swx_core.services.billing.exchange_rate_service.currency_repository") as mock_currency:
                mock_rates.get_latest = AsyncMock(side_effect=[SimpleNamespace(rate=1500.0), None, SimpleNamespace(rate=2.0), None, None])
                mock_currency.get_base_currency = AsyncMock(return_value=SimpleNamespace(code="USD"))
                mock_currency.get_by_code = AsyncMock(return_value=None)
                mock_rates.get_rates_map = AsyncMock(return_value={"KES": 129.5, "NGN": 1500.0})
                direct = await exchange_rate_service.get_rate(session, "USD", "NGN")
                inverse = await exchange_rate_service.get_rate(session, "NGN", "USD")
                pivot = await exchange_rate_service.get_rate(session, "KES", "NGN")

        assert direct == 1500.0
        assert inverse == 0.5
        assert round(pivot, 6) == round(1500.0 / 129.5, 6)

    async def test_tax_calculation_for_multiple_jurisdictions(self):
        ng = tax_service.calculate_tax(100_000, "NG")
        gb = tax_service.calculate_tax(100_000, "GB")
        us = tax_service.calculate_tax(100_000, "US")

        assert ng == {"amount": 100000, "tax_rate": 7.5, "tax_amount": 7500, "total": 107500}
        assert gb["tax_amount"] == 20000
        assert us["total"] == 100000
