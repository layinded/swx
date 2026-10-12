from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.services.billing import billing_service
from swx_core.services.billing.usage_window_service import (
    QuotaStatus,
    get_usage_window_service,
)


async def get_quota_status_controller(session: AsyncSession, user_id: UUID) -> QuotaStatus:
    account = await billing_service.get_user_billing_account(session, user_id)
    account_id = account.id if account else user_id
    monthly_quota = await billing_service.get_plan_monthly_quota(session, user_id)
    service = get_usage_window_service()
    return await service.get_status(account_id, monthly_quota=monthly_quota)


async def reset_quota_window_controller(session: AsyncSession, user_id: UUID) -> QuotaStatus:
    account = await billing_service.get_user_billing_account(session, user_id)
    account_id = account.id if account else user_id
    monthly_quota = await billing_service.get_plan_monthly_quota(session, user_id)
    service = get_usage_window_service()
    return await service.reset_window(account_id)
