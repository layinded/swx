"""
Access Review Service
---------------------
SOC 2 CC6.2 / CC6.1 access review report generation.

Generates structured reports on:
- Orphaned accounts (active users with no recent login)
- Unused roles (role assignments with no recent RBAC activity)
- Stale tokens (refresh tokens older than threshold, still valid)
- Over-provisioned users (admin role holders with no admin activity)

Controller → Service → Repository pattern.  All DB queries in the repository.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.repositories import access_review_repository
from swx_core.services.audit_logger import AuditLogger, ActorType, AuditOutcome, AuditAction


async def get_access_review_service(
    session: AsyncSession,
    days_inactive: int = 90,
    days_unused: int = 90,
    days_stale: int = 30,
    days_over_provisioned: int = 30,
) -> dict:
    """Generate a full access review report."""
    report = await access_review_repository.get_access_review_summary(
        session,
        days_inactive=days_inactive,
        days_unused=days_unused,
        days_stale=days_stale,
        days_over_provisioned=days_over_provisioned,
    )

    await event_bus.dispatch(
        "compliance.access_review_generated",
        payload={
            "orphaned_count": report["orphaned_accounts"]["count"],
            "unused_role_count": report["unused_roles"]["count"],
            "stale_token_count": report["stale_tokens"]["count"],
            "over_provisioned_count": report["over_provisioned_users"]["count"],
        },
    )

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.ADMIN_USER_CREATED,  # closest existing admin action
        actor_type=ActorType.SYSTEM,
        resource_type="access_review",
        outcome=AuditOutcome.SUCCESS,
        context={
            "event": "access_review_generated",
            "orphaned_count": report["orphaned_accounts"]["count"],
            "unused_role_count": report["unused_roles"]["count"],
            "stale_token_count": report["stale_tokens"]["count"],
            "over_provisioned_count": report["over_provisioned_users"]["count"],
        },
    )

    return report


async def get_orphaned_accounts_service(
    session: AsyncSession, days_inactive: int = 90
) -> list[dict]:
    """Find active users with no login within the given period."""
    users = await access_review_repository.find_orphaned_accounts(
        session, days_inactive=days_inactive
    )
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


async def get_unused_roles_service(
    session: AsyncSession, days_unused: int = 90
) -> list[dict]:
    """Find role assignments with no RBAC audit activity within the period."""
    return await access_review_repository.find_unused_roles(session, days_unused)


async def get_stale_tokens_service(
    session: AsyncSession, days_old: int = 30
) -> list[dict]:
    """Find refresh tokens older than threshold that are still valid."""
    tokens = await access_review_repository.find_stale_tokens(session, days_old)
    return [
        {
            "id": str(t.id),
            "user_email": t.user_email,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        }
        for t in tokens
    ]


async def get_over_provisioned_users_service(
    session: AsyncSession, days: int = 30
) -> list[dict]:
    """Find users with admin roles but no admin activity within the period."""
    return await access_review_repository.find_over_provisioned_users(session, days)