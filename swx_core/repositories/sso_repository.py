# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false, reportMissingImports=false

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ..models.sso_provider import SSOProvider
from ..models.sso_session import SSOSession


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _apply_updates(instance: Any, updates: dict[str, Any]) -> Any:
    for field_name, value in updates.items():
        setattr(instance, field_name, value)
    return instance


async def create_provider(session: AsyncSession, data: dict[str, Any]) -> SSOProvider:
    provider = SSOProvider(**data)
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return provider


async def get_provider_by_id(session: AsyncSession, provider_id: UUID) -> SSOProvider | None:
    return await session.get(SSOProvider, provider_id)


async def list_providers(session: AsyncSession, *, enabled: bool | None = None, skip: int = 0, limit: int = 100) -> list[SSOProvider]:
    stmt = select(SSOProvider)
    if enabled is not None:
        stmt = stmt.where(SSOProvider.enabled == enabled)
    stmt = stmt.order_by(SSOProvider.name.asc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_provider(session: AsyncSession, provider_id: UUID, data: dict[str, Any]) -> SSOProvider | None:
    provider = await get_provider_by_id(session, provider_id)
    if provider is None:
        return None
    _apply_updates(provider, {**data, "updated_at": utc_now_naive()})
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return provider


async def delete_provider(session: AsyncSession, provider_id: UUID) -> bool:
    provider = await get_provider_by_id(session, provider_id)
    if provider is None:
        return False
    await session.delete(provider)
    await session.commit()
    return True


async def get_provider_by_domain(session: AsyncSession, domain: str) -> SSOProvider | None:
    stmt = select(SSOProvider).where(func.lower(SSOProvider.domain) == domain.lower()).order_by(SSOProvider.enabled.desc(), SSOProvider.name.asc())
    return (await session.execute(stmt)).scalars().first()


async def create_session(session: AsyncSession, data: dict[str, Any]) -> SSOSession:
    sso_session = SSOSession(**data)
    session.add(sso_session)
    await session.commit()
    await session.refresh(sso_session)
    return sso_session


async def get_session_by_id(session: AsyncSession, sso_session_id: UUID) -> SSOSession | None:
    return await session.get(SSOSession, sso_session_id)


async def list_sessions(session: AsyncSession, *, user_id: UUID | None = None, provider_id: UUID | None = None, status: str | None = None, skip: int = 0, limit: int = 100) -> list[SSOSession]:
    stmt = select(SSOSession)
    if user_id is not None:
        stmt = stmt.where(SSOSession.user_id == user_id)
    if provider_id is not None:
        stmt = stmt.where(SSOSession.provider_id == provider_id)
    if status is not None:
        stmt = stmt.where(SSOSession.status == status)
    stmt = stmt.order_by(SSOSession.updated_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_session(session: AsyncSession, sso_session_id: UUID, data: dict[str, Any]) -> SSOSession | None:
    sso_session = await get_session_by_id(session, sso_session_id)
    if sso_session is None:
        return None
    _apply_updates(sso_session, {**data, "updated_at": utc_now_naive()})
    session.add(sso_session)
    await session.commit()
    await session.refresh(sso_session)
    return sso_session


async def terminate_session(session: AsyncSession, sso_session_id: UUID) -> SSOSession | None:
    return await update_session(session, sso_session_id, {"status": "terminated"})


async def get_active_session_by_user(session: AsyncSession, user_id: UUID, provider_id: UUID | None = None) -> SSOSession | None:
    stmt = select(SSOSession).where(SSOSession.user_id == user_id, SSOSession.status == "active")
    if provider_id is not None:
        stmt = stmt.where(SSOSession.provider_id == provider_id)
    stmt = stmt.order_by(SSOSession.updated_at.desc())
    return (await session.execute(stmt)).scalars().first()
