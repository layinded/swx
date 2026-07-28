# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.service_component import ServiceComponentCreate, ServiceComponentPublic, ServiceComponentUpdate
from swx_core.repositories import status_repository


async def create_component(session: AsyncSession, data: ServiceComponentCreate) -> ServiceComponentPublic:
    component_data: dict[str, Any] = data.model_dump(exclude_unset=True)
    component = await status_repository.create_component(session, component_data)
    await event_bus.dispatch("status.component_created", payload={"component_id": str(component.id), "name": component.name})
    return ServiceComponentPublic.model_validate(component)


async def get_component(session: AsyncSession, component_id: UUID) -> ServiceComponentPublic:
    component = await status_repository.get_component_by_id(session, component_id)
    if component is None:
        raise ValueError("Component not found")
    return ServiceComponentPublic.model_validate(component)


async def list_components(session: AsyncSession, group: str | None = None, skip: int = 0, limit: int = 50) -> list[ServiceComponentPublic]:
    components = await status_repository.list_components(session, group=group, skip=skip, limit=limit)
    return [ServiceComponentPublic.model_validate(c) for c in components]


async def update_component(session: AsyncSession, component_id: UUID, data: ServiceComponentUpdate) -> ServiceComponentPublic:
    component = await status_repository.get_component_by_id(session, component_id)
    if component is None:
        raise ValueError("Component not found")
    updated = await status_repository.update_component(session, component_id, data.model_dump(exclude_unset=True))
    await event_bus.dispatch("status.component_updated", payload={"component_id": str(component_id)})
    return ServiceComponentPublic.model_validate(updated or component)


async def delete_component(session: AsyncSession, component_id: UUID) -> ServiceComponentPublic:
    component = await status_repository.get_component_by_id(session, component_id)
    if component is None:
        raise ValueError("Component not found")
    deleted = await status_repository.delete_component(session, component_id)
    await event_bus.dispatch("status.component_deleted", payload={"component_id": str(component_id)})
    return ServiceComponentPublic.model_validate(deleted)