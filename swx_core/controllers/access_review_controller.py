"""
Access Review Controller
-----------------------
HTTP layer for SOC 2 CC6.2 access review endpoints.

Controller → Service → Repository pattern.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.services.compliance.access_review_service import (
    get_access_review_service,
    get_orphaned_accounts_service,
    get_unused_roles_service,
    get_stale_tokens_service,
    get_over_provisioned_users_service,
)


async def get_access_review_controller(
    session: AsyncSession,
    days_inactive: int = 90,
    days_unused: int = 90,
    days_stale: int = 30,
    days_over_provisioned: int = 30,
) -> dict:
    return await get_access_review_service(
        session,
        days_inactive=days_inactive,
        days_unused=days_unused,
        days_stale=days_stale,
        days_over_provisioned=days_over_provisioned,
    )


async def get_orphaned_accounts_controller(
    session: AsyncSession, days_inactive: int = 90
) -> list[dict]:
    return await get_orphaned_accounts_service(session, days_inactive)


async def get_unused_roles_controller(
    session: AsyncSession, days_unused: int = 90
) -> list[dict]:
    return await get_unused_roles_service(session, days_unused)


async def get_stale_tokens_controller(
    session: AsyncSession, days_old: int = 30
) -> list[dict]:
    return await get_stale_tokens_service(session, days_old)


async def get_over_provisioned_users_controller(
    session: AsyncSession, days: int = 30
) -> list[dict]:
    return await get_over_provisioned_users_service(session, days)