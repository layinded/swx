# pyright: reportExplicitAny=false, reportAny=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportUnnecessaryTypeIgnoreComment=false

from typing import Any, Optional
from uuid import UUID
from swx_core.utils.time import utc_now

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, select, func

from swx_core.models.api_key_scope import ApiKey, ApiKeyScope

async def create_api_key(session: AsyncSession, data: dict[str, Any]) -> ApiKey:
    key = ApiKey(**data)
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key

async def get_api_key_by_hash(session: AsyncSession, hashed_key: str) -> ApiKey | None:
    stmt = select(ApiKey).where(ApiKey.hashed_key == hashed_key)
    return (await session.execute(stmt)).scalar_one_or_none()

async def get_api_key_by_prefix(session: AsyncSession, key_prefix: str) -> list[ApiKey]:
    stmt = select(ApiKey).where(ApiKey.key_prefix == key_prefix).order_by(desc(ApiKey.created_at))
    return list((await session.execute(stmt)).scalars().all())

async def get_api_key_by_id(session: AsyncSession, key_id: UUID) -> ApiKey | None:
    return await session.get(ApiKey, key_id)

async def list_api_keys(
    session: AsyncSession,
    user_id: UUID | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[ApiKey]:
    stmt = select(ApiKey)
    if user_id:
        stmt = stmt.where(ApiKey.user_id == user_id)
    if is_active is not None:
        stmt = stmt.where(ApiKey.is_active == is_active)
    stmt = stmt.order_by(desc(ApiKey.created_at)).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def count_api_keys(session: AsyncSession, user_id: UUID | None = None, is_active: bool | None = None) -> int:
    stmt = select(func.count()).select_from(ApiKey)
    if user_id:
        stmt = stmt.where(ApiKey.user_id == user_id)
    if is_active is not None:
        stmt = stmt.where(ApiKey.is_active == is_active)
    return int((await session.execute(stmt)).scalar() or 0)

async def deactivate_api_key(session: AsyncSession, key_id: UUID) -> ApiKey | None:
    key = await get_api_key_by_id(session, key_id)
    if key is None:
        return None
    key.is_active = False
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key

async def update_last_used(session: AsyncSession, key_id: UUID) -> None:
    key = await get_api_key_by_id(session, key_id)
    if key:
        key.last_used_at = utc_now()
        session.add(key)
        await session.commit()

async def add_scopes(session: AsyncSession, api_key_id: UUID, scopes: list[dict[str, str]]) -> list[ApiKeyScope]:
    created: list[ApiKeyScope] = []
    for scope in scopes:
        s = ApiKeyScope(api_key_id=api_key_id, resource=scope["resource"], action=scope["action"])
        session.add(s)
        created.append(s)
    await session.commit()
    for s in created:
        await session.refresh(s)
    return created

async def remove_scopes(session: AsyncSession, api_key_id: UUID, scope_ids: list[UUID]) -> int:
    from sqlalchemy import delete
    stmt = delete(ApiKeyScope).where(ApiKeyScope.api_key_id == api_key_id, ApiKeyScope.id.in_(scope_ids))
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)

async def get_scopes_for_key(session: AsyncSession, api_key_id: UUID) -> list[ApiKeyScope]:
    stmt = select(ApiKeyScope).where(ApiKeyScope.api_key_id == api_key_id, ApiKeyScope.is_active == True)  # noqa: E712
    return list((await session.execute(stmt)).scalars().all())

async def check_scope(session: AsyncSession, api_key_id: UUID, resource: str, action: str) -> bool:
    scopes = await get_scopes_for_key(session, api_key_id)
    for scope in scopes:
        if scope.resource in (resource, "*") and scope.action in (action, "*"):
            return True
    return False