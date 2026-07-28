# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.feature_flag import FeatureFlagCreate, FeatureFlagPublic, FeatureFlagUpdate
from swx_core.repositories import feature_flag_repository


async def create_flag(session: AsyncSession, data: FeatureFlagCreate) -> FeatureFlagPublic:
    flag_data: dict[str, Any] = data.model_dump(exclude_unset=True)
    flag = await feature_flag_repository.create_flag(session, flag_data)
    await event_bus.dispatch("feature_flag.created", payload={"flag_id": str(flag.id), "key": flag.key})
    return FeatureFlagPublic.model_validate(flag)


async def get_flag(session: AsyncSession, flag_id: UUID) -> FeatureFlagPublic:
    flag = await feature_flag_repository.get_flag_by_id(session, flag_id)
    if flag is None:
        raise ValueError("Feature flag not found")
    return FeatureFlagPublic.model_validate(flag)


async def get_flag_by_key(session: AsyncSession, key: str) -> FeatureFlagPublic:
    flag = await feature_flag_repository.get_flag_by_key(session, key)
    if flag is None:
        raise ValueError("Feature flag not found")
    return FeatureFlagPublic.model_validate(flag)


async def list_flags(session: AsyncSession, enabled: bool | None = None, skip: int = 0, limit: int = 50) -> list[FeatureFlagPublic]:
    flags = await feature_flag_repository.list_flags(session, enabled=enabled, skip=skip, limit=limit)
    return [FeatureFlagPublic.model_validate(f) for f in flags]


async def update_flag(session: AsyncSession, flag_id: UUID, data: FeatureFlagUpdate) -> FeatureFlagPublic:
    flag = await feature_flag_repository.get_flag_by_id(session, flag_id)
    if flag is None:
        raise ValueError("Feature flag not found")
    updated = await feature_flag_repository.update_flag(session, flag_id, data.model_dump(exclude_unset=True))
    await event_bus.dispatch("feature_flag.updated", payload={"flag_id": str(flag_id), "key": flag.key})
    return FeatureFlagPublic.model_validate(updated or flag)


async def delete_flag(session: AsyncSession, flag_id: UUID) -> FeatureFlagPublic:
    flag = await feature_flag_repository.get_flag_by_id(session, flag_id)
    if flag is None:
        raise ValueError("Feature flag not found")
    deleted = await feature_flag_repository.delete_flag(session, flag_id)
    await event_bus.dispatch("feature_flag.deleted", payload={"flag_id": str(flag_id), "key": flag.key})
    return FeatureFlagPublic.model_validate(deleted)