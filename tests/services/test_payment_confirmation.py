"""Unit tests for payment_confirmation_service (SWX-021).

Tests parse_reference_prefix, _provider_amount_to_nano, confirm_payment
idempotency, and apply_payment routing — all without a real DB or Redis.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swx_core.services.billing.payment_confirmation_service import (
    PaymentConfirmResult,
    _provider_amount_to_nano,
    apply_payment,
    confirm_payment,
    parse_reference_prefix,
)


# ---------------------------------------------------------------------------
# parse_reference_prefix
# ---------------------------------------------------------------------------


class TestParseReferencePrefix:
    def test_plan_reference(self):
        prefix, key = parse_reference_prefix("plan-pro-v1-a1b2c3d4")
        assert prefix == "plan"
        assert key == "pro-v1"

    def test_pack_reference(self):
        prefix, key = parse_reference_prefix("pack-credits-50-b2c3d4e5")
        assert prefix == "pack"
        assert key == "credits-50"

    def test_unknown_prefix(self):
        prefix, key = parse_reference_prefix("order-abc-123")
        assert prefix == ""
        assert key is None

    def test_too_short_reference(self):
        prefix, key = parse_reference_prefix("plan-abc")
        assert prefix == ""
        assert key is None

    def test_single_char_key(self):
        prefix, key = parse_reference_prefix("plan-x-a1b2c3d4")
        assert prefix == "plan"
        assert key == "x"

    def test_empty_string(self):
        prefix, key = parse_reference_prefix("")
        assert prefix == ""
        assert key is None


# ---------------------------------------------------------------------------
# _provider_amount_to_nano
# ---------------------------------------------------------------------------


class TestProviderAmountToNano:
    def test_paystack_kobo_to_nano(self):
        # 50000 kobo = 500 NGN = 5_000_000_000 nano
        assert _provider_amount_to_nano("paystack", 50000) == 5_000_000_000

    def test_flutterwave_kobo_to_nano(self):
        assert _provider_amount_to_nano("flutterwave", 50000) == 5_000_000_000

    def test_unknown_provider_passthrough(self):
        assert _provider_amount_to_nano("stripe", 1000) == 1000


# ---------------------------------------------------------------------------
# apply_payment
# ---------------------------------------------------------------------------


class TestApplyPayment:
    @pytest.mark.asyncio
    async def test_plan_purchase_creates_subscription(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        mock_account = SimpleNamespace(id=uuid.uuid4())

        with patch("swx_core.services.billing.payment_confirmation_service.SubscriptionService") as MockSubSvc:
            mock_sub = AsyncMock()
            mock_sub.get_or_create_account = AsyncMock(return_value=mock_account)
            mock_sub.create_subscription = AsyncMock()
            MockSubSvc.return_value = mock_sub

            await apply_payment(session, user_id, "plan-pro-v1-abc", 0, "NGN", "plan", "pro-v1")

            mock_sub.get_or_create_account.assert_called_once_with(user_id, "user")
            mock_sub.create_subscription.assert_called_once_with(mock_account.id, "pro-v1", allow_paid=True)

    @pytest.mark.asyncio
    async def test_pack_purchase_credits_wallet(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        mock_account = SimpleNamespace(id=uuid.uuid4())
        amount_nano = 5_000_000_000

        with patch("swx_core.services.billing.payment_confirmation_service.SubscriptionService") as MockSubSvc, \
             patch("swx_core.services.billing.payment_confirmation_service.wallet_service") as mock_wallet:
            mock_sub = AsyncMock()
            mock_sub.get_or_create_account = AsyncMock(return_value=mock_account)
            MockSubSvc.return_value = mock_sub
            mock_wallet.credit_wallet = AsyncMock()

            await apply_payment(
                session, user_id, "pack-credits-50-abc",
                amount_nano, "NGN", "pack", "credits-50",
            )

            mock_wallet.credit_wallet.assert_called_once_with(
                session, mock_account.id, "NGN", amount_nano,
                "pack-credits-50-abc", "pack-credits-50-abc",
            )

    @pytest.mark.asyncio
    async def test_unrecognized_reference_credits_wallet(self):
        """When parse_reference_prefix returns ('', None), treat as wallet credit."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        mock_account = SimpleNamespace(id=uuid.uuid4())
        amount_nano = 3_000_000_000

        with patch("swx_core.services.billing.payment_confirmation_service.SubscriptionService") as MockSubSvc, \
             patch("swx_core.services.billing.payment_confirmation_service.wallet_service") as mock_wallet:
            mock_sub = AsyncMock()
            mock_sub.get_or_create_account = AsyncMock(return_value=mock_account)
            MockSubSvc.return_value = mock_sub
            mock_wallet.credit_wallet = AsyncMock()

            await apply_payment(
                session, user_id, "txn-12345",
                amount_nano, "NGN", "", None,
            )

            mock_wallet.credit_wallet.assert_called_once()


# ---------------------------------------------------------------------------
# confirm_payment
# ---------------------------------------------------------------------------


class TestConfirmPayment:
    @pytest.mark.asyncio
    async def test_provider_verification_fails(self):
        session = AsyncMock()
        user_id = uuid.uuid4()

        with patch("swx_core.services.billing.payment_confirmation_service.get_local_payment_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.verify_payment = AsyncMock(side_effect=ConnectionError("timeout"))
            mock_factory.return_value = mock_provider

            result = await confirm_payment(session, user_id, "paystack", "plan-pro-v1-abc")

            assert result.status == "error"
            assert "Provider verification failed" in result.message
            assert result.reference == "plan-pro-v1-abc"

    @pytest.mark.asyncio
    async def test_payment_not_paid(self):
        session = AsyncMock()
        user_id = uuid.uuid4()

        with patch("swx_core.services.billing.payment_confirmation_service.get_local_payment_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.verify_payment = AsyncMock(return_value={"status": "failed", "paid": False})
            mock_factory.return_value = mock_provider

            result = await confirm_payment(session, user_id, "paystack", "plan-pro-v1-abc")

            assert result.status == "not_paid"
            assert result.provider == "paystack"

    @pytest.mark.asyncio
    async def test_duplicate_payment_skipped(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        redis_client = AsyncMock()
        redis_client.exists = AsyncMock(return_value=True)

        with patch("swx_core.services.billing.payment_confirmation_service.get_local_payment_provider") as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.verify_payment = AsyncMock(return_value={"status": "success", "paid": True, "raw": {}})
            mock_factory.return_value = mock_provider

            result = await confirm_payment(session, user_id, "paystack", "plan-pro-v1-abc", redis_client)

            assert result.status == "duplicate"
            assert result.applied is True

    @pytest.mark.asyncio
    async def test_successful_plan_confirmation(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        redis_client = AsyncMock()
        redis_client.exists = AsyncMock(return_value=False)
        redis_client.setex = AsyncMock()

        with patch("swx_core.services.billing.payment_confirmation_service.get_local_payment_provider") as mock_factory, \
             patch("swx_core.services.billing.payment_confirmation_service.apply_payment", new_callable=AsyncMock) as mock_apply:

            mock_provider = AsyncMock()
            mock_provider.verify_payment = AsyncMock(return_value={
                "status": "success", "paid": True,
                "raw": {"amount": 50000, "currency": "NGN"},
            })
            mock_factory.return_value = mock_provider

            result = await confirm_payment(
                session, user_id, "paystack", "plan-pro-v1-abc", redis_client,
            )

            assert result.status == "success"
            assert result.applied is True
            assert result.purchase_type == "plan"
            assert result.item_key == "pro-v1"
            mock_apply.assert_called_once()
            redis_client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_pack_confirmation(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        redis_client = AsyncMock()
        redis_client.exists = AsyncMock(return_value=False)
        redis_client.setex = AsyncMock()

        with patch("swx_core.services.billing.payment_confirmation_service.get_local_payment_provider") as mock_factory, \
             patch("swx_core.services.billing.payment_confirmation_service.apply_payment", new_callable=AsyncMock) as mock_apply:

            mock_provider = AsyncMock()
            mock_provider.verify_payment = AsyncMock(return_value={
                "status": "success", "paid": True,
                "raw": {"amount": 30000, "currency": "NGN"},
            })
            mock_factory.return_value = mock_provider

            result = await confirm_payment(
                session, user_id, "flutterwave", "pack-credits-50-xyz", redis_client,
            )

            assert result.status == "success"
            assert result.purchase_type == "pack"
            assert result.item_key == "credits-50"
            mock_apply.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_failure_rolls_back(self):
        session = AsyncMock()
        user_id = uuid.uuid4()
        redis_client = AsyncMock()
        redis_client.exists = AsyncMock(return_value=False)

        with patch("swx_core.services.billing.payment_confirmation_service.get_local_payment_provider") as mock_factory, \
             patch("swx_core.services.billing.payment_confirmation_service.apply_payment", new_callable=AsyncMock, side_effect=RuntimeError("db error")):

            mock_provider = AsyncMock()
            mock_provider.verify_payment = AsyncMock(return_value={
                "status": "success", "paid": True,
                "raw": {"amount": 50000, "currency": "NGN"},
            })
            mock_factory.return_value = mock_provider

            result = await confirm_payment(
                session, user_id, "paystack", "plan-pro-v1-abc", redis_client,
            )

            assert result.status == "error"
            assert "Failed to apply" in result.message
            session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_redis_still_works(self):
        """Confirm payment works without Redis (no idempotency, but no crash)."""
        session = AsyncMock()
        user_id = uuid.uuid4()

        with patch("swx_core.services.billing.payment_confirmation_service.get_local_payment_provider") as mock_factory, \
             patch("swx_core.services.billing.payment_confirmation_service.apply_payment", new_callable=AsyncMock) as mock_apply:

            mock_provider = AsyncMock()
            mock_provider.verify_payment = AsyncMock(return_value={
                "status": "success", "paid": True,
                "raw": {"amount": 50000, "currency": "NGN"},
            })
            mock_factory.return_value = mock_provider

            result = await confirm_payment(
                session, user_id, "paystack", "plan-pro-v1-abc", redis_client=None,
            )

            assert result.status == "success"
            assert result.applied is True