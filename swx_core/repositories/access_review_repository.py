"""
Access Review Repository
-----------------------
Database queries for SOC 2 CC6.2 access review reporting.

All database queries live here (SWX Controller → Service → Repository pattern).
"""

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select, distinct, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.audit_log import AuditLog
from swx_core.models.refresh_token import RefreshToken
from swx_core.models.role import Role
from swx_core.models.user import User
from swx_core.models.user_role import UserRole


async def find_orphaned_accounts(
    session: AsyncSession, days_inactive: int = 90
) -> list[User]:
    """
    Find active users with no login audit event within the given period.

    An "orphaned account" is an active user who has not logged in for
    ``days_inactive`` days.  We check the audit log for any
    ``auth.login_success`` event; users with no matching entry are flagged.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_inactive)

    # Users who logged in within the window (subquery returning actor_id values)
    recent_login_actor_ids = (
        select(AuditLog.actor_id)  # type: ignore[union-attr]
        .where(
            AuditLog.action == "auth.login_success",
            AuditLog.timestamp >= cutoff,
        )
        .distinct()
    )

    # Active users NOT in the recent login set
    stmt = (
        select(User)
        .where(
            User.is_active == True,  # noqa: E712
            User.id.not_in(recent_login_actor_ids),
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_unused_roles(
    session: AsyncSession, days_unused: int = 90
) -> list[dict]:
    """
    Find roles assigned but never exercised (no audit log entry) within the period.

    Returns a list of dicts with role info and the user it is assigned to.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_unused)

    # Roles that appear in RBAC audit events within the window (subquery)
    used_role_ids_stmt = (
        select(AuditLog.resource_id)  # type: ignore[union-attr]
        .where(
            AuditLog.action.in_(["rbac.role_assigned", "rbac.role_removed"]),
            AuditLog.timestamp >= cutoff,
        )
        .distinct()
    )

    # UserRole assignments where the role has no recent RBAC activity
    stmt = (
        select(UserRole, Role)
        .join(Role, UserRole.role_id == Role.id)
        .where(Role.id.not_in(used_role_ids_stmt))
    )
    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "user_id": str(row.UserRole.user_id),
            "role_id": str(row.UserRole.role_id),
            "role_name": row.Role.name,
            "role_domain": row.Role.domain,
            "team_id": str(row.UserRole.team_id) if row.UserRole.team_id else None,
        }
        for row in rows
    ]


async def find_stale_tokens(
    session: AsyncSession, days_old: int = 30
) -> list[RefreshToken]:
    """
    Find refresh tokens older than ``days_old`` days that are still valid
    (i.e., not yet expired).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
    now = datetime.now(timezone.utc)

    stmt = (
        select(RefreshToken)
        .where(
            RefreshToken.created_at <= cutoff,
            RefreshToken.expires_at > now,
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_over_provisioned_users(
    session: AsyncSession, days: int = 30
) -> list[dict]:
    """
    Find users with admin-level roles but no admin audit log activity within
    ``days`` days — indicating over-provisioned access.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Admin role IDs (domain = 'admin')
    admin_role_ids_stmt = (
        select(Role.id).where(Role.domain == "admin")
    )

    # Users assigned an admin role
    admin_user_role_stmt = (
        select(UserRole)
        .where(UserRole.role_id.in_(admin_role_ids_stmt))
    )
    admin_ur_result = await session.execute(admin_user_role_stmt)
    admin_assignments = list(admin_ur_result.scalars().all())

    # Filter to those with NO admin activity in the audit log
    over_provisioned = []
    for assignment in admin_assignments:
        recent_admin_activity = await session.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.actor_id == str(assignment.user_id),
                AuditLog.action.like("admin.%"),  # type: ignore[union-attr]
                AuditLog.timestamp >= cutoff,
            )
        )
        count = recent_admin_activity.scalar() or 0
        if count == 0:
            # Look up the user
            user = await session.get(User, assignment.user_id)
            role = await session.get(Role, assignment.role_id)
            if user and role:
                over_provisioned.append({
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "role_id": str(role.id),
                    "role_name": role.name,
                    "last_admin_activity": None,
                })

    return over_provisioned


async def get_access_review_summary(
    session: AsyncSession,
    days_inactive: int = 90,
    days_unused: int = 90,
    days_stale: int = 30,
    days_over_provisioned: int = 30,
) -> dict:
    """Aggregate all access review findings into a single report."""
    orphaned = await find_orphaned_accounts(session, days_inactive)
    unused = await find_unused_roles(session, days_unused)
    stale = await find_stale_tokens(session, days_stale)
    over_prov = await find_over_provisioned_users(session, days_over_provisioned)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "days_inactive": days_inactive,
            "days_unused": days_unused,
            "days_stale": days_stale,
            "days_over_provisioned": days_over_provisioned,
        },
        "orphaned_accounts": {
            "count": len(orphaned),
            "users": [
                {
                    "id": str(u.id),
                    "email": u.email,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in orphaned
            ],
        },
        "unused_roles": {
            "count": len(unused),
            "assignments": unused,
        },
        "stale_tokens": {
            "count": len(stale),
            "tokens": [
                {
                    "id": str(t.id),
                    "user_email": t.user_email,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                }
                for t in stale
            ],
        },
        "over_provisioned_users": {
            "count": len(over_prov),
            "users": over_prov,
        },
    }