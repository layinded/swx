"""
Refresh Token Management
------------------------
This module provides functions for managing refresh tokens in the authentication system.

Features:
- Supports token revocation for session invalidation.

Methods:
- `revoke_refresh_token()`: Deletes a refresh token from the database.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from swx_core.models.refresh_token import RefreshToken


async def revoke_refresh_token(session: AsyncSession, token_str: str) -> bool:
    """
    Revoke a refresh token by removing it from the database.

    Args:
        session (AsyncSession): The database session.
        token_str (str): The refresh token string to be revoked.

    Returns:
        bool: True if the token was successfully revoked, False if the token was not found.
    """
    statement = select(RefreshToken).where(RefreshToken.token == token_str)
    result = await session.execute(statement)
    token = result.scalar_one_or_none()
    if not token:
        return False
    await session.delete(token)
    await session.commit()
    return True
