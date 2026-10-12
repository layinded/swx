# pyright: reportExplicitAny=false, reportAny=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from uuid import UUID
from datetime import datetime

from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.mfa import MfaRecoveryCode
from swx_core.models.user import User
from swx_core.utils.time import utc_now


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def update_mfa_status(session: AsyncSession, user_id: UUID, enabled: bool, secret: str | None = None) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.mfa_enabled = enabled
    if secret is not None:
        user.mfa_secret = secret
    if not enabled:
        user.mfa_secret = None
        user.mfa_verified_at = None
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def set_mfa_verified_at(session: AsyncSession, user_id: UUID) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.mfa_verified_at = utc_now()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def set_mfa_secret(session: AsyncSession, user_id: UUID, secret: str) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.mfa_secret = secret
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_recovery_codes(session: AsyncSession, user_id: UUID, code_hashes: list[str]) -> list[MfaRecoveryCode]:
    codes = [MfaRecoveryCode(user_id=user_id, code_hash=h) for h in code_hashes]
    session.add_all(codes)
    await session.commit()
    for code in codes:
        await session.refresh(code)
    return codes


async def get_unused_recovery_codes(session: AsyncSession, user_id: UUID) -> list[MfaRecoveryCode]:
    stmt = select(MfaRecoveryCode).where(
        MfaRecoveryCode.user_id == user_id,
        MfaRecoveryCode.used_at.is_(None),  # pyright: ignore[reportAttributeAccessIssue]
    )
    return list((await session.execute(stmt)).scalars().all())


async def mark_recovery_code_used(session: AsyncSession, code_id: UUID) -> MfaRecoveryCode | None:
    code = await session.get(MfaRecoveryCode, code_id)
    if code is None:
        return None
    code.used_at = utc_now()
    session.add(code)
    await session.commit()
    await session.refresh(code)
    return code


async def delete_all_recovery_codes(session: AsyncSession, user_id: UUID) -> int:
    stmt = sql_delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0