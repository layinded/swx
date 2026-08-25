"""Usage metering service — records token usage and debits wallets.

Calculates cost based on per-model pricing, records usage in the rolling
window, and debits the user's wallet idempotently. Quota enforcement:
Free plan raises QuotaExceededError (429), Paid plan raises 402 on overflow.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.services.billing import wallet_service
from swx_core.services.billing.usage_window_service import get_usage_window_service
from swx_core.utils.errors import QuotaExceededError


def calculate_cost_nano(input_tokens: int, output_tokens: int, model_key: str) -> int:
    pricing_table = settings.USAGE_METERING_MODEL_PRICING
    fallback_key = settings.USAGE_METERING_DEFAULT_MODEL_KEY
    pricing = pricing_table.get(model_key, pricing_table.get(fallback_key, {"input": 0, "output": 0}))
    return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])


class UsageMeteringService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._window_service = get_usage_window_service()

    async def record_and_charge(
        self,
        account_id: UUID,
        model_key: str,
        input_tokens: int,
        output_tokens: int,
        request_id: str,
        currency: str | None = None,
    ) -> int:
        charge_currency = currency or settings.USAGE_METERING_DEFAULT_CURRENCY
        cost_nano = calculate_cost_nano(input_tokens, output_tokens, model_key)

        await self._window_service.record_usage(account_id, input_tokens + output_tokens)

        quota_status = await self._window_service.get_status(account_id)
        if quota_status.window_remaining <= 0:
            raise QuotaExceededError(resource="usage_window", message="Usage window quota exceeded")
        if quota_status.monthly_remaining <= 0:
            raise QuotaExceededError(resource="monthly_quota", message="Monthly quota exceeded")

        charge_key = uuid4().hex
        reference = f"usage-{request_id}-{charge_key}"
        idempotency_key = f"usage-{request_id}-{charge_key}"
        await wallet_service.debit_wallet(
            self.session, account_id, charge_currency, cost_nano, reference, idempotency_key
        )

        return cost_nano


def get_usage_metering_service(session: AsyncSession) -> UsageMeteringService:
    return UsageMeteringService(session)