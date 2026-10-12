"""Refresh token repository — DB operations only (SWX pattern).

All business logic (JWT creation, validation, encryption) lives in
the service layer. This module provides only database read/persist
operations for refresh tokens.
"""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.refresh_token import RefreshToken
from swx_core.utils.time import utc_now


async def find_token_by_email(session: AsyncSession, email: str) -> RefreshToken | None:
    """Find the most recent refresh token for a user email (ordered by created_at desc)."""
    stmt = (
        select(RefreshToken)
        .where(RefreshToken.user_email == email)
        .order_by(RefreshToken.created_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def find_all_tokens_by_email(session: AsyncSession, email: str) -> list[RefreshToken]:
    """Find all refresh tokens for a user email, ordered by created_at desc."""
    stmt = (
        select(RefreshToken)
        .where(RefreshToken.user_email == email)
        .order_by(RefreshToken.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_token_by_raw_value(session: AsyncSession, raw_token: str) -> RefreshToken | None:
    """Find a token by its raw stored value (fallback for non-encrypted setups)."""
    stmt = select(RefreshToken).where(RefreshToken.token == raw_token)
    result = await session.execute(stmt)
    return result.scalars().first()


async def update_existing_token(
    session: AsyncSession,
    token: RefreshToken,
    encrypted_value: str,
    expires_at: datetime,
    last_activity_at: datetime,
    device_info: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Update an existing refresh token's fields and commit."""
    token.token = encrypted_value
    token.expires_at = expires_at
    token.last_activity_at = last_activity_at
    if device_info is not None:
        token.device_info = device_info
    if ip_address is not None:
        token.ip_address = ip_address
    session.add(token)
    await session.commit()


async def create_token(session: AsyncSession, token: RefreshToken) -> None:
    """Insert a new refresh token and commit."""
    session.add(token)
    await session.commit()


async def delete_token(session: AsyncSession, token: RefreshToken) -> None:
    """Delete a single refresh token and commit."""
    await session.delete(token)
    await session.commit()


async def delete_all_tokens_by_email(session: AsyncSession, email: str) -> int:
    """Delete all refresh tokens for a user email. Returns count deleted."""
    stmt = delete(RefreshToken).where(RefreshToken.user_email == email)
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)