from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.service_component import ServiceComponentCreate, ServiceComponentPublic, ServiceComponentUpdate
from swx_core.models.status_incident import StatusIncidentCreate, StatusIncidentPublic, StatusIncidentUpdate
from swx_core.models.incident_update import IncidentUpdateCreate, IncidentUpdatePublic
from swx_core.services.status import status_component_service, status_incident_service


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def create_component_controller(session: AsyncSession, data: ServiceComponentCreate) -> ServiceComponentPublic:
    return await status_component_service.create_component(session, data)


async def get_component_controller(session: AsyncSession, component_id: UUID) -> ServiceComponentPublic:
    try:
        return await status_component_service.get_component(session, component_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_components_controller(session: AsyncSession, group: str | None = None, skip: int = 0, limit: int = 50) -> list[ServiceComponentPublic]:
    return await status_component_service.list_components(session, group=group, skip=skip, limit=limit)


async def update_component_controller(session: AsyncSession, component_id: UUID, data: ServiceComponentUpdate) -> ServiceComponentPublic:
    try:
        return await status_component_service.update_component(session, component_id, data)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def delete_component_controller(session: AsyncSession, component_id: UUID) -> ServiceComponentPublic:
    try:
        return await status_component_service.delete_component(session, component_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def create_incident_controller(session: AsyncSession, admin_id: UUID, data: StatusIncidentCreate) -> StatusIncidentPublic:
    return await status_incident_service.create_incident(session, admin_id, data)


async def get_incident_controller(session: AsyncSession, incident_id: UUID) -> StatusIncidentPublic:
    try:
        return await status_incident_service.get_incident(session, incident_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_incidents_controller(session: AsyncSession, status: str | None = None, component_id: UUID | None = None, skip: int = 0, limit: int = 50) -> list[StatusIncidentPublic]:
    return await status_incident_service.list_incidents(session, status=status, component_id=component_id, skip=skip, limit=limit)


async def update_incident_controller(session: AsyncSession, incident_id: UUID, data: StatusIncidentUpdate) -> StatusIncidentPublic:
    try:
        return await status_incident_service.update_incident(session, incident_id, data)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def resolve_incident_controller(session: AsyncSession, incident_id: UUID) -> StatusIncidentPublic:
    try:
        return await status_incident_service.resolve_incident(session, incident_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def add_incident_update_controller(session: AsyncSession, incident_id: UUID, admin_id: UUID, data: IncidentUpdateCreate) -> IncidentUpdatePublic:
    try:
        return await status_incident_service.add_incident_update(session, incident_id, admin_id, data)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def get_status_summary_controller(session: AsyncSession) -> dict[str, Any]:
    return await status_incident_service.get_status_summary(session)