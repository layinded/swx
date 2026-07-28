# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.content_filter import ContentFilter, ContentFilterCreate, ContentFilterPublic, ContentFilterUpdate
from swx_core.repositories import safety_repository
from swx_core.services.safety.safety_cache import invalidate_cache


async def _get_filter_or_raise(session: AsyncSession, filter_id: UUID) -> ContentFilter:
    content_filter = await safety_repository.get_filter_by_id(session, filter_id)
    if content_filter is None:
        raise ValueError("Content filter not found")
    return content_filter


async def create_filter(session: AsyncSession, body: ContentFilterCreate) -> ContentFilterPublic:
    content_filter = await safety_repository.create_filter(session, body.model_dump(exclude_unset=True))
    invalidate_cache()
    await event_bus.dispatch("safety.filter_created", payload={"filter_id": str(content_filter.id), "name": content_filter.name})
    return ContentFilterPublic.model_validate(content_filter)


async def get_filter(session: AsyncSession, filter_id: UUID) -> ContentFilterPublic:
    return ContentFilterPublic.model_validate(await _get_filter_or_raise(session, filter_id))


async def list_filters(session: AsyncSession, enabled: bool | None = None, category: str | None = None, skip: int = 0, limit: int = 100) -> list[ContentFilterPublic]:
    filters = await safety_repository.list_filters(session, enabled=enabled, category=category, skip=skip, limit=limit)
    return [ContentFilterPublic.model_validate(content_filter) for content_filter in filters]


async def update_filter(session: AsyncSession, filter_id: UUID, body: ContentFilterUpdate) -> ContentFilterPublic:
    await _get_filter_or_raise(session, filter_id)
    updated_filter = await safety_repository.update_filter(session, filter_id, body.model_dump(exclude_unset=True))
    invalidate_cache()
    await event_bus.dispatch("safety.filter_updated", payload={"filter_id": str(filter_id)})
    return ContentFilterPublic.model_validate(updated_filter)


async def delete_filter(session: AsyncSession, filter_id: UUID) -> ContentFilterPublic:
    content_filter = await _get_filter_or_raise(session, filter_id)
    deleted_filter = await safety_repository.delete_filter(session, filter_id)
    invalidate_cache()
    await event_bus.dispatch("safety.filter_deleted", payload={"filter_id": str(filter_id), "name": content_filter.name})
    return ContentFilterPublic.model_validate(deleted_filter or content_filter)
