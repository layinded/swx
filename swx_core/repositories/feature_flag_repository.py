# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false, reportAttributeAccessIssue=false

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.feature_flag import FeatureFlag
from swx_core.models.flag_evaluation import FlagEvaluation


def _apply_updates(instance: Any, updates: dict[str, Any]) -> Any:
    for field_name, value in updates.items():
        setattr(instance, field_name, value)
    return instance


# --- Feature Flag ---


async def create_flag(session: AsyncSession, data: dict[str, Any]) -> FeatureFlag:
    flag = FeatureFlag(**data)
    session.add(flag)
    await session.commit()
    await session.refresh(flag)
    return flag


async def get_flag_by_id(session: AsyncSession, flag_id: UUID) -> FeatureFlag | None:
    return await session.get(FeatureFlag, flag_id)


async def get_flag_by_key(session: AsyncSession, key: str) -> FeatureFlag | None:
    stmt = select(FeatureFlag).where(FeatureFlag.key == key)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_flags(session: AsyncSession, *, enabled: bool | None = None, skip: int = 0, limit: int = 50) -> list[FeatureFlag]:
    stmt = select(FeatureFlag)
    if enabled is not None:
        stmt = stmt.where(FeatureFlag.enabled == enabled)
    stmt = stmt.order_by(FeatureFlag.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_flag(session: AsyncSession, flag_id: UUID, data: dict[str, Any]) -> FeatureFlag | None:
    flag = await get_flag_by_id(session, flag_id)
    if flag is None:
        return None
    _apply_updates(flag, {**data, "updated_at": datetime.utcnow()})
    session.add(flag)
    await session.commit()
    await session.refresh(flag)
    return flag


async def delete_flag(session: AsyncSession, flag_id: UUID) -> FeatureFlag | None:
    flag = await get_flag_by_id(session, flag_id)
    if flag is None:
        return None
    await session.delete(flag)
    await session.commit()
    return flag


async def get_flag_count(session: AsyncSession, *, enabled: bool | None = None) -> int:
    stmt = select(func.count()).select_from(FeatureFlag)
    if enabled is not None:
        stmt = stmt.where(FeatureFlag.enabled == enabled)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


# --- Flag Evaluation ---


async def create_evaluation(session: AsyncSession, data: dict[str, Any]) -> FlagEvaluation:
    evaluation = FlagEvaluation(**data)
    session.add(evaluation)
    await session.commit()
    await session.refresh(evaluation)
    return evaluation


async def get_evaluation_by_id(session: AsyncSession, evaluation_id: UUID) -> FlagEvaluation | None:
    return await session.get(FlagEvaluation, evaluation_id)


async def list_evaluations(session: AsyncSession, *, flag_id: UUID | None = None, user_id: UUID | None = None, skip: int = 0, limit: int = 50) -> list[FlagEvaluation]:
    stmt = select(FlagEvaluation)
    if flag_id is not None:
        stmt = stmt.where(FlagEvaluation.flag_id == flag_id)
    if user_id is not None:
        stmt = stmt.where(FlagEvaluation.user_id == user_id)
    stmt = stmt.order_by(FlagEvaluation.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_evaluation_count(session: AsyncSession, *, flag_id: UUID | None = None) -> int:
    stmt = select(func.count()).select_from(FlagEvaluation)
    if flag_id is not None:
        stmt = stmt.where(FlagEvaluation.flag_id == flag_id)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)