# pyright: reportMissingTypeArgument=false

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.controllers.status_controller import (
    get_status_summary_controller,
    list_components_controller,
    list_incidents_controller,
    get_incident_controller,
)
from swx_core.database.db import get_session
from swx_core.models.service_component import ServiceComponentPublic
from swx_core.models.status_incident import StatusIncidentPublic

router = APIRouter(prefix="/status", tags=["User - Status Page"])


@router.get("/summary")
async def get_status_summary(
    session: AsyncSession = Depends(get_session),
):
    return await get_status_summary_controller(session)


@router.get("/components", response_model=list[ServiceComponentPublic])
async def list_components(
    group: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    return await list_components_controller(session, group=group, skip=skip, limit=limit)


@router.get("/incidents", response_model=list[StatusIncidentPublic])
async def list_incidents(
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    return await list_incidents_controller(session, status=status, skip=skip, limit=limit)


@router.get("/incidents/{incident_id}", response_model=StatusIncidentPublic)
async def get_incident(
    incident_id: str,
    session: AsyncSession = Depends(get_session),
):
    from uuid import UUID
    return await get_incident_controller(session, UUID(incident_id))