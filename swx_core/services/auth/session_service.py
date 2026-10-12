"""Session management service — SOC 2 CC6.1 concurrent limits and idle timeout.

Enforces max concurrent sessions per user, provides session listing/revocation,
and expires idle sessions.
"""

from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.models.refresh_token import SessionPublic
from swx_core.repositories import session_repository as repo
from swx_core.services.audit_logger import AuditLogger, AuditAction, ActorType, AuditOutcome
from swx_core.utils.time import utc_now


async def list_sessions(session: AsyncSession, user_email: str) -> list[SessionPublic]:
    tokens = await repo.list_active_sessions(session, user_email)
    now = utc_now()
    return [
        SessionPublic(
            id=t.id,
            user_email=t.user_email,
            device_info=t.device_info,
            ip_address=t.ip_address,
            created_at=t.created_at,
            last_activity_at=t.last_activity_at,
            expires_at=t.expires_at,
            is_expired=t.expires_at < now,
        )
        for t in tokens
    ]


async def revoke_session(session: AsyncSession, token_id: UUID, user_email: str) -> bool:
    result = await repo.revoke_session(session, token_id)
    if result:
        audit = AuditLogger(session)
        await audit.log_event(
            action=AuditAction.AUTH_SESSION_REVOKED,
            actor_type=ActorType.USER,
            actor_id=user_email,
            resource_type="session",
            resource_id=str(token_id),
            outcome=AuditOutcome.SUCCESS,
        )
        await event_bus.dispatch("auth.session_revoked", payload={"token_id": str(token_id), "user_email": user_email})
    return result


async def revoke_all_sessions(session: AsyncSession, user_email: str) -> int:
    count = await repo.revoke_all_sessions(session, user_email)
    if count > 0:
        audit = AuditLogger(session)
        await audit.log_event(
            action=AuditAction.AUTH_SESSION_REVOKED,
            actor_type=ActorType.USER,
            actor_id=user_email,
            resource_type="session",
            resource_id="all",
            outcome=AuditOutcome.SUCCESS,
            context={"sessions_revoked": count},
        )
        await event_bus.dispatch("auth.all_sessions_revoked", payload={"user_email": user_email, "count": count})
    return count


async def enforce_concurrent_limit(session: AsyncSession, user_email: str) -> int:
    max_sessions = settings.MAX_CONCURRENT_SESSIONS  # pyright: ignore[reportAttributeAccessIssue]
    current = await repo.count_active_sessions(session, user_email)
    if current < max_sessions:
        return 0
    revoked = await repo.revoke_oldest_sessions(session, user_email, keep=max_sessions - 1)
    if revoked > 0:
        audit = AuditLogger(session)
        await audit.log_event(
            action=AuditAction.AUTH_SESSION_LIMIT_ENFORCED,
            actor_type=ActorType.SYSTEM,
            actor_id=user_email,
            resource_type="session",
            resource_id="concurrent_limit",
            outcome=AuditOutcome.SUCCESS,
            context={"max_sessions": max_sessions, "revoked_count": revoked},
        )
        await event_bus.dispatch("auth.session_limit_enforced", payload={"user_email": user_email, "revoked": revoked})
    return revoked


async def expire_idle_sessions(session: AsyncSession) -> int:
    timeout_minutes = settings.SESSION_IDLE_TIMEOUT_MINUTES  # pyright: ignore[reportAttributeAccessIssue]
    idle_before = utc_now() - timedelta(minutes=timeout_minutes)
    idle_tokens = await repo.find_idle_sessions(session, idle_before)
    if not idle_tokens:
        return 0
    count = await repo.batch_delete_sessions(session, idle_tokens)
    audit = AuditLogger(session)
    for token in idle_tokens:
        await audit.log_event(
            action=AuditAction.AUTH_SESSION_EXPIRED_IDLE,
            actor_type=ActorType.SYSTEM,
            resource_type="session",
            resource_id=str(token.id),
            outcome=AuditOutcome.SUCCESS,
            context={"idle_minutes": timeout_minutes},
        )
    logger.info("Expired %d idle sessions (timeout=%d minutes)", count, timeout_minutes)
    return count


async def update_session_activity(session: AsyncSession, token_id: UUID) -> None:
    await repo.update_last_activity(session, token_id)


async def session_idle_cleanup_loop() -> None:
    """Background task that periodically expires idle sessions."""
    import asyncio
    interval = settings.SESSION_IDLE_CLEANUP_INTERVAL_SECONDS  # pyright: ignore[reportAttributeAccessIssue]
    while True:
        await asyncio.sleep(interval)
        try:
            from swx_core.database.db import async_session
            async with async_session() as session:
                await expire_idle_sessions(session)
        except Exception:
            logger.warning("Idle session cleanup failed, will retry next cycle")