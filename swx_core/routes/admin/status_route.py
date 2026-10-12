# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.admin.dependencies import AdminUserDep
from swx_core.controllers.status_controller import (
    add_incident_update_controller,
    create_component_controller,
    create_incident_controller,
    delete_component_controller,
    get_component_controller,
    get_incident_controller,
    list_components_controller,
    list_incidents_controller,
    resolve_incident_controller,
    update_component_controller,
    update_incident_controller,
)
from swx_core.database.db import get_session
from swx_core.models.service_component import ServiceComponentCreate, ServiceComponentPublic, ServiceComponentUpdate
from swx_core.models.status_incident import StatusIncidentCreate, StatusIncidentPublic, StatusIncidentUpdate
from swx_core.models.incident_update import IncidentUpdateCreate, IncidentUpdatePublic

router = APIRouter(prefix="/admin/status", tags=["Admin - Status Page"])


@router.get("/components", response_model=list[ServiceComponentPublic])
async def list_components(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    group: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_components_controller(session, group=group, skip=skip, limit=limit)


@router.post("/components", response_model=ServiceComponentPublic, status_code=201)
async def create_component(
    _admin: AdminUserDep,
    body: ServiceComponentCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_component_controller(session, body)


@router.get("/components/{component_id}", response_model=ServiceComponentPublic)
async def get_component(
    _admin: AdminUserDep,
    component_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_component_controller(session, component_id)


@router.put("/components/{component_id}", response_model=ServiceComponentPublic)
async def update_component(
    _admin: AdminUserDep,
    component_id: UUID,
    body: ServiceComponentUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_component_controller(session, component_id, body)


@router.delete("/components/{component_id}", response_model=ServiceComponentPublic)
async def delete_component(
    _admin: AdminUserDep,
    component_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await delete_component_controller(session, component_id)


@router.get("/incidents", response_model=list[StatusIncidentPublic])
async def list_incidents(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None),
    component_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_incidents_controller(session, status=status, component_id=component_id, skip=skip, limit=limit)


@router.post("/incidents", response_model=StatusIncidentPublic, status_code=201)
async def create_incident(
    _admin: AdminUserDep,
    body: StatusIncidentCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_incident_controller(session, _admin.id, body)


@router.get("/incidents/{incident_id}", response_model=StatusIncidentPublic)
async def get_incident(
    _admin: AdminUserDep,
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_incident_controller(session, incident_id)


@router.put("/incidents/{incident_id}", response_model=StatusIncidentPublic)
async def update_incident(
    _admin: AdminUserDep,
    incident_id: UUID,
    body: StatusIncidentUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_incident_controller(session, incident_id, body)


@router.put("/incidents/{incident_id}/resolve", response_model=StatusIncidentPublic)
async def resolve_incident(
    _admin: AdminUserDep,
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await resolve_incident_controller(session, incident_id)


@router.post("/incidents/{incident_id}/updates", response_model=IncidentUpdatePublic, status_code=201)
async def add_incident_update(
    _admin: AdminUserDep,
    incident_id: UUID,
    body: IncidentUpdateCreate,
    session: AsyncSession = Depends(get_session),
):
    return await add_incident_update_controller(session, incident_id, _admin.id, body)