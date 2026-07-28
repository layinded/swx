# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false, reportAttributeAccessIssue=false

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.service_component import ServiceComponent
from swx_core.models.status_incident import StatusIncident
from swx_core.models.incident_update import IncidentUpdate


def _apply_updates(instance: Any, updates: dict[str, Any]) -> Any:
    for field_name, value in updates.items():
        setattr(instance, field_name, value)
    return instance


# --- Service Component ---


async def create_component(session: AsyncSession, data: dict[str, Any]) -> ServiceComponent:
    component = ServiceComponent(**data)
    session.add(component)
    await session.commit()
    await session.refresh(component)
    return component


async def get_component_by_id(session: AsyncSession, component_id: UUID) -> ServiceComponent | None:
    return await session.get(ServiceComponent, component_id)


async def list_components(session: AsyncSession, *, group: str | None = None, skip: int = 0, limit: int = 50) -> list[ServiceComponent]:
    stmt = select(ServiceComponent)
    if group is not None:
        stmt = stmt.where(ServiceComponent.group_name == group)
    stmt = stmt.order_by(ServiceComponent.sort_order.asc(), ServiceComponent.name.asc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_component(session: AsyncSession, component_id: UUID, data: dict[str, Any]) -> ServiceComponent | None:
    component = await get_component_by_id(session, component_id)
    if component is None:
        return None
    _apply_updates(component, {**data, "updated_at": datetime.utcnow()})
    session.add(component)
    await session.commit()
    await session.refresh(component)
    return component


async def delete_component(session: AsyncSession, component_id: UUID) -> ServiceComponent | None:
    component = await get_component_by_id(session, component_id)
    if component is None:
        return None
    await session.delete(component)
    await session.commit()
    return component


async def get_component_count(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(ServiceComponent)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


# --- Status Incident ---


async def create_incident(session: AsyncSession, data: dict[str, Any]) -> StatusIncident:
    incident = StatusIncident(**data)
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return incident


async def get_incident_by_id(session: AsyncSession, incident_id: UUID) -> StatusIncident | None:
    return await session.get(StatusIncident, incident_id)


async def list_incidents(session: AsyncSession, *, status: str | None = None, component_id: UUID | None = None, skip: int = 0, limit: int = 50) -> list[StatusIncident]:
    stmt = select(StatusIncident)
    if status is not None:
        stmt = stmt.where(StatusIncident.status == status)
    if component_id is not None:
        stmt = stmt.where(StatusIncident.component_id == component_id)
    stmt = stmt.order_by(StatusIncident.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_incident(session: AsyncSession, incident_id: UUID, data: dict[str, Any]) -> StatusIncident | None:
    incident = await get_incident_by_id(session, incident_id)
    if incident is None:
        return None
    _apply_updates(incident, {**data, "updated_at": datetime.utcnow()})
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return incident


async def get_active_incidents(session: AsyncSession, *, skip: int = 0, limit: int = 50) -> list[StatusIncident]:
    stmt = select(StatusIncident).where(StatusIncident.status.notin_(["resolved", "postmortem"]))
    stmt = stmt.order_by(StatusIncident.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_incident_count(session: AsyncSession, *, status: str | None = None) -> int:
    stmt = select(func.count()).select_from(StatusIncident)
    if status is not None:
        stmt = stmt.where(StatusIncident.status == status)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


# --- Incident Update ---


async def create_incident_update(session: AsyncSession, data: dict[str, Any]) -> IncidentUpdate:
    update = IncidentUpdate(**data)
    session.add(update)
    await session.commit()
    await session.refresh(update)
    return update


async def list_incident_updates(session: AsyncSession, *, incident_id: UUID, skip: int = 0, limit: int = 50) -> list[IncidentUpdate]:
    stmt = (
        select(IncidentUpdate)
        .where(IncidentUpdate.incident_id == incident_id)
        .order_by(IncidentUpdate.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())