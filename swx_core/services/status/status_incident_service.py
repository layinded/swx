# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.service_component import ServiceComponentPublic as SCPublic
from swx_core.models.status_incident import StatusIncidentCreate, StatusIncidentPublic, StatusIncidentUpdate
from swx_core.models.incident_update import IncidentUpdateCreate, IncidentUpdatePublic
from swx_core.repositories import status_repository


async def create_incident(session: AsyncSession, admin_id: UUID, data: StatusIncidentCreate) -> StatusIncidentPublic:
    incident_data: dict[str, Any] = {**data.model_dump(exclude_unset=True), "created_by": admin_id}
    if "started_at" not in incident_data or incident_data.get("started_at") is None:
        incident_data["started_at"] = datetime.utcnow()
    incident = await status_repository.create_incident(session, incident_data)
    await event_bus.dispatch("status.incident_created", payload={"incident_id": str(incident.id), "severity": incident.severity})
    return StatusIncidentPublic.model_validate(incident)


async def get_incident(session: AsyncSession, incident_id: UUID) -> StatusIncidentPublic:
    incident = await status_repository.get_incident_by_id(session, incident_id)
    if incident is None:
        raise ValueError("Incident not found")
    return StatusIncidentPublic.model_validate(incident)


async def list_incidents(session: AsyncSession, status: str | None = None, component_id: UUID | None = None, skip: int = 0, limit: int = 50) -> list[StatusIncidentPublic]:
    incidents = await status_repository.list_incidents(session, status=status, component_id=component_id, skip=skip, limit=limit)
    return [StatusIncidentPublic.model_validate(i) for i in incidents]


async def update_incident(session: AsyncSession, incident_id: UUID, data: StatusIncidentUpdate) -> StatusIncidentPublic:
    incident = await status_repository.get_incident_by_id(session, incident_id)
    if incident is None:
        raise ValueError("Incident not found")
    updated = await status_repository.update_incident(session, incident_id, data.model_dump(exclude_unset=True))
    await event_bus.dispatch("status.incident_updated", payload={"incident_id": str(incident_id)})
    return StatusIncidentPublic.model_validate(updated or incident)


async def resolve_incident(session: AsyncSession, incident_id: UUID) -> StatusIncidentPublic:
    incident = await status_repository.get_incident_by_id(session, incident_id)
    if incident is None:
        raise ValueError("Incident not found")
    updated = await status_repository.update_incident(session, incident_id, {"status": "resolved", "resolved_at": datetime.utcnow()})
    await event_bus.dispatch("status.incident_resolved", payload={"incident_id": str(incident_id)})
    return StatusIncidentPublic.model_validate(updated or incident)


async def add_incident_update(session: AsyncSession, incident_id: UUID, admin_id: UUID, data: IncidentUpdateCreate) -> IncidentUpdatePublic:
    incident = await status_repository.get_incident_by_id(session, incident_id)
    if incident is None:
        raise ValueError("Incident not found")
    update_data: dict[str, Any] = {**data.model_dump(exclude_unset=True), "incident_id": incident_id, "created_by": admin_id}
    update = await status_repository.create_incident_update(session, update_data)
    await status_repository.update_incident(session, incident_id, {"status": data.status, "updated_at": datetime.utcnow()})
    await event_bus.dispatch("status.incident_update_added", payload={"incident_id": str(incident_id), "update_id": str(update.id)})
    return IncidentUpdatePublic.model_validate(update)


async def get_status_summary(session: AsyncSession) -> dict[str, Any]:
    components = await status_repository.list_components(session, skip=0, limit=200)
    active_incidents = await status_repository.get_active_incidents(session, skip=0, limit=50)
    return {
        "components": [SCPublic.model_validate(c).model_dump() for c in components],
        "active_incidents": [StatusIncidentPublic.model_validate(i).model_dump() for i in active_incidents],
    }