# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false, reportAttributeAccessIssue=false

from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.content_filter import ContentFilter
from swx_core.models.safety_check import SafetyCheck


def _apply_updates(instance: Any, updates: dict[str, Any]) -> Any:
    for field_name, value in updates.items():
        setattr(instance, field_name, value)
    return instance


async def create_filter(session: AsyncSession, data: dict[str, Any]) -> ContentFilter:
    content_filter = ContentFilter(**data)
    session.add(content_filter)
    await session.commit()
    await session.refresh(content_filter)
    return content_filter


async def get_filter_by_id(session: AsyncSession, filter_id: UUID) -> ContentFilter | None:
    return await session.get(ContentFilter, filter_id)


async def list_filters(session: AsyncSession, *, enabled: bool | None = None, category: str | None = None, skip: int = 0, limit: int = 100) -> list[ContentFilter]:
    stmt = select(ContentFilter)
    if enabled is not None:
        stmt = stmt.where(ContentFilter.enabled == enabled)
    if category is not None:
        stmt = stmt.where(ContentFilter.category == category)
    stmt = stmt.order_by(ContentFilter.updated_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_filter(session: AsyncSession, filter_id: UUID, data: dict[str, Any]) -> ContentFilter | None:
    content_filter = await get_filter_by_id(session, filter_id)
    if content_filter is None:
        return None
    _apply_updates(content_filter, data)
    session.add(content_filter)
    await session.commit()
    await session.refresh(content_filter)
    return content_filter


async def delete_filter(session: AsyncSession, filter_id: UUID) -> ContentFilter | None:
    content_filter = await get_filter_by_id(session, filter_id)
    if content_filter is None:
        return None
    await session.delete(content_filter)
    await session.commit()
    return content_filter


async def create_check(session: AsyncSession, data: dict[str, Any]) -> SafetyCheck:
    safety_check = SafetyCheck(**data)
    session.add(safety_check)
    await session.commit()
    await session.refresh(safety_check)
    return safety_check


async def get_check_by_id(session: AsyncSession, check_id: UUID) -> SafetyCheck | None:
    return await session.get(SafetyCheck, check_id)


async def list_checks(session: AsyncSession, *, user_id: UUID | None = None, overall_verdict: str | None = None, skip: int = 0, limit: int = 100) -> list[SafetyCheck]:
    stmt = select(SafetyCheck)
    if user_id is not None:
        stmt = stmt.where(SafetyCheck.user_id == user_id)
    if overall_verdict is not None:
        stmt = stmt.where(SafetyCheck.overall_verdict == overall_verdict)
    stmt = stmt.order_by(SafetyCheck.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_check_count(session: AsyncSession, *, user_id: UUID | None = None, overall_verdict: str | None = None) -> int:
    stmt = select(func.count()).select_from(SafetyCheck)
    if user_id is not None:
        stmt = stmt.where(SafetyCheck.user_id == user_id)
    if overall_verdict is not None:
        stmt = stmt.where(SafetyCheck.overall_verdict == overall_verdict)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


async def list_checks_by_user(session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100) -> list[SafetyCheck]:
    return await list_checks(session, user_id=user_id, skip=skip, limit=limit)


async def list_checks_by_verdict(session: AsyncSession, overall_verdict: str, skip: int = 0, limit: int = 100) -> list[SafetyCheck]:
    return await list_checks(session, overall_verdict=overall_verdict, skip=skip, limit=limit)
