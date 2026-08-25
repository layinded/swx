"""Session repository — DB operations for refresh token sessions (SOC 2 CC6.1)."""

from uuid import UUID
from datetime import datetime

from sqlalchemy import delete, select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.refresh_token import RefreshToken
from swx_core.utils.time import utc_now


async def count_active_sessions(session: AsyncSession, user_email: str) -> int:
    now = utc_now()
    stmt = select(func.count()).select_from(RefreshToken).where(
        RefreshToken.user_email == user_email,
        RefreshToken.expires_at > now,
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def list_active_sessions(session: AsyncSession, user_email: str) -> list[RefreshToken]:
    now = utc_now()
    stmt = (
        select(RefreshToken)
        .where(RefreshToken.user_email == user_email, RefreshToken.expires_at > now)
        .order_by(RefreshToken.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_session_by_id(session: AsyncSession, token_id: UUID) -> RefreshToken | None:
    return await session.get(RefreshToken, token_id)


async def revoke_session(session: AsyncSession, token_id: UUID) -> bool:
    token = await get_session_by_id(session, token_id)
    if token is None:
        return False
    await session.delete(token)
    await session.commit()
    return True


async def revoke_all_sessions(session: AsyncSession, user_email: str) -> int:
    stmt = delete(RefreshToken).where(RefreshToken.user_email == user_email)
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)


async def revoke_oldest_sessions(session: AsyncSession, user_email: str, keep: int) -> int:
    now = utc_now()
    stmt = (
        select(RefreshToken.id)
        .where(RefreshToken.user_email == user_email, RefreshToken.expires_at > now)
        .order_by(RefreshToken.created_at.desc())
        .offset(keep)
    )
    result = await session.execute(stmt)
    ids_to_revoke = list(result.scalars().all())
    if not ids_to_revoke:
        return 0
    delete_stmt = delete(RefreshToken).where(RefreshToken.id.in_(ids_to_revoke))
    delete_result = await session.execute(delete_stmt)
    await session.commit()
    return int(delete_result.rowcount or 0)


async def update_last_activity(session: AsyncSession, token_id: UUID) -> None:
    token = await get_session_by_id(session, token_id)
    if token is not None:
        token.last_activity_at = utc_now()
        session.add(token)
        await session.commit()


async def find_idle_sessions(session: AsyncSession, idle_before: datetime) -> list[RefreshToken]:
    now = utc_now()
    stmt = select(RefreshToken).where(
        RefreshToken.expires_at > now,
        or_(
            RefreshToken.last_activity_at == None,  # noqa: E711
            RefreshToken.last_activity_at < idle_before,
        ),
    )
    return list((await session.execute(stmt)).scalars().all())


async def batch_delete_sessions(session: AsyncSession, sessions: list[RefreshToken]) -> int:
    if not sessions:
        return 0
    ids = [s.id for s in sessions]
    stmt = delete(RefreshToken).where(RefreshToken.id.in_(ids))
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)