"""API key lifecycle service — SOC 2 CC6.1 expiry and inactive revocation."""

import asyncio
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.models.api_key_scope import ApiKey
from swx_core.repositories import api_key_scope_repository as repo
from swx_core.services.audit_logger import AuditLogger, ActorType, AuditOutcome, AuditAction
from swx_core.utils.time import utc_now


async def _audit_revoked_keys(session: AsyncSession, keys: list[ApiKey], action: AuditAction, reason: str) -> None:
    audit = AuditLogger(session)
    for key in keys:
        await audit.log_event(
            action=action,
            actor_type=ActorType.SYSTEM,
            resource_type="api_key",
            resource_id=str(key.id),
            outcome=AuditOutcome.SUCCESS,
            context={"reason": reason},
        )


async def revoke_expired_api_keys(session: AsyncSession) -> dict[str, object]:
    now = utc_now()

    expired_keys = await repo.find_expired_keys(session, now)
    expired_count = await repo.batch_deactivate_keys(session, expired_keys)
    for key in expired_keys:
        await event_bus.dispatch("api_key.expired", payload={"key_id": str(key.id), "user_id": str(key.user_id)})
    await _audit_revoked_keys(session, expired_keys, AuditAction.API_KEY_EXPIRED, "expired")

    inactive_threshold = now - timedelta(days=settings.API_KEY_MAX_INACTIVE_DAYS)  # pyright: ignore[reportAttributeAccessIssue]
    inactive_keys = await repo.find_inactive_keys(session, inactive_threshold)
    inactive_revoked_count = await repo.batch_deactivate_keys(session, inactive_keys)
    for key in inactive_keys:
        await event_bus.dispatch("api_key.inactive_revoked", payload={"key_id": str(key.id), "user_id": str(key.user_id)})
    await _audit_revoked_keys(session, inactive_keys, AuditAction.API_KEY_INACTIVE_REVOKED, "inactive_revoked")

    logger.info("API key lifecycle cleanup: %d expired, %d inactive revoked", expired_count, inactive_revoked_count)

    return {
        "expired_count": expired_count,
        "inactive_revoked_count": inactive_revoked_count,
        "total_revoked": expired_count + inactive_revoked_count,
    }


async def api_key_lifecycle_loop() -> None:
    interval = settings.API_KEY_LIFECYCLE_INTERVAL_SECONDS  # pyright: ignore[reportAttributeAccessIssue]
    while True:
        await asyncio.sleep(interval)
        try:
            from swx_core.database.db import async_session
            async with async_session() as session:
                await revoke_expired_api_keys(session)
        except Exception:
            logger.warning("API key lifecycle cleanup failed, will retry next cycle")