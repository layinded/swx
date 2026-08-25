from fastapi import HTTPException, Request, Depends
from datetime import timedelta

from swx_core.auth.user.dependencies import get_current_user
from swx_core.config.settings import settings
from swx_core.database.db import SessionDep
from swx_core.models.user import User
from swx_core.services.auth import session_service as svc
from swx_core.utils.time import utc_now


async def enforce_idle_timeout(
    request: Request,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
) -> User:
    timeout_minutes = settings.SESSION_IDLE_TIMEOUT_MINUTES  # pyright: ignore[reportAttributeAccessIssue]

    sessions = await svc.list_sessions(session, current_user.email)
    if not sessions:
        return current_user

    active = sessions[0]
    if active.last_activity_at is not None:
        idle_limit = utc_now() - timedelta(minutes=timeout_minutes)
        if active.last_activity_at < idle_limit:
            await svc.revoke_all_sessions(session, current_user.email)
            raise HTTPException(status_code=401, detail="Session expired due to inactivity. Please log in again.")

    await svc.update_session_activity(session, active.id)
    return current_user