"""Session management controller — SOC 2 CC6.1."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.refresh_token import SessionPublic
from swx_core.services.auth import session_service


async def list_sessions_controller(session: AsyncSession, user_email: str) -> list[SessionPublic]:
    return await session_service.list_sessions(session, user_email)


async def revoke_session_controller(session: AsyncSession, token_id: UUID, user_email: str) -> dict[str, object]:
    result = await session_service.revoke_session(session, token_id, user_email)
    if not result:
        return {"status": "not_found", "token_id": str(token_id)}
    return {"status": "revoked", "token_id": str(token_id)}


async def revoke_all_sessions_controller(session: AsyncSession, user_email: str) -> dict[str, object]:
    count = await session_service.revoke_all_sessions(session, user_email)
    return {"status": "revoked_all", "count": count}