# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.admin.dependencies import get_current_admin_user
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

router = APIRouter(prefix="/status", tags=["Admin - Status Page"])


@router.get("/components", response_model=list[ServiceComponentPublic])
async def list_components(
    group: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await list_components_controller(session, group=group, skip=skip, limit=limit)


@router.post("/components", response_model=ServiceComponentPublic, status_code=201)
async def create_component(
    body: ServiceComponentCreate,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await create_component_controller(session, body)


@router.get("/components/{component_id}", response_model=ServiceComponentPublic)
async def get_component(
    component_id: UUID,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await get_component_controller(session, component_id)


@router.put("/components/{component_id}", response_model=ServiceComponentPublic)
async def update_component(
    component_id: UUID,
    body: ServiceComponentUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await update_component_controller(session, component_id, body)


@router.delete("/components/{component_id}", response_model=ServiceComponentPublic)
async def delete_component(
    component_id: UUID,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await delete_component_controller(session, component_id)


@router.get("/incidents", response_model=list[StatusIncidentPublic])
async def list_incidents(
    status: str | None = Query(default=None),
    component_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await list_incidents_controller(session, status=status, component_id=component_id, skip=skip, limit=limit)


@router.post("/incidents", response_model=StatusIncidentPublic, status_code=201)
async def create_incident(
    body: StatusIncidentCreate,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    admin_id = UUID(_admin["id"]) if isinstance(_admin, dict) else _admin.id
    return await create_incident_controller(session, admin_id, body)


@router.get("/incidents/{incident_id}", response_model=StatusIncidentPublic)
async def get_incident(
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await get_incident_controller(session, incident_id)


@router.put("/incidents/{incident_id}", response_model=StatusIncidentPublic)
async def update_incident(
    incident_id: UUID,
    body: StatusIncidentUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await update_incident_controller(session, incident_id, body)


@router.put("/incidents/{incident_id}/resolve", response_model=StatusIncidentPublic)
async def resolve_incident(
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await resolve_incident_controller(session, incident_id)


@router.post("/incidents/{incident_id}/updates", response_model=IncidentUpdatePublic, status_code=201)
async def add_incident_update(
    incident_id: UUID,
    body: IncidentUpdateCreate,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    admin_id = UUID(_admin["id"]) if isinstance(_admin, dict) else _admin.id
    return await add_incident_update_controller(session, incident_id, admin_id, body)