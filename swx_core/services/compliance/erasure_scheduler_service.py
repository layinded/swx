# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

"""Erasure Scheduler Service
----------------------------
SOC 2 CC6.5: Executes scheduled GDPR erasures for users past their grace period.

Queries swx_users via erasure_repository where gdpr_deleted_at <= now()
and is_active = False, then calls erasure_service.execute_erasure() for each.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.repositories import erasure_repository
from swx_core.services.compliance.erasure_service import execute_erasure


async def execute_scheduled_erasures(session: AsyncSession) -> dict:
    """Execute erasure for all users past their grace period."""
    users = await erasure_repository.find_users_due_for_erasure(session)
    results: list[dict] = []
    errors: list[dict] = []

    for user in users:
        try:
            result = await execute_erasure(session, user.id)
            results.append({"user_id": str(user.id), "status": result.get("status", "unknown")})
        except Exception as e:
            logger.error(f"Failed to execute erasure for user {user.id}: {e}")
            errors.append({"user_id": str(user.id), "error": str(e)})

    await event_bus.dispatch(
        "compliance.scheduled_erasure_completed",
        payload={
            "total": len(users),
            "completed": len(results),
            "errors": len(errors),
        },
    )

    return {
        "total": len(users),
        "completed": len(results),
        "errors": len(errors),
        "details": results,
        "error_details": errors,
    }