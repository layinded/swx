# pyright: reportMissingTypeArgument=false, reportMissingImports=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.admin.dependencies import AdminUserDep
from ...controllers.sso_controller import create_provider_controller, delete_provider_controller, get_provider_controller, list_providers_controller, list_sessions_controller, terminate_session_controller, update_provider_controller
from ...database.db import get_session
from ...models.sso_provider import SSOProviderCreate, SSOProviderPublic, SSOProviderUpdate
from ...models.sso_session import SSOSessionPublic

router = APIRouter(prefix="/admin/sso", tags=["Admin - SSO"])


@router.get("/providers", response_model=list[SSOProviderPublic])
async def list_providers(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    return await list_providers_controller(session, skip=skip, limit=limit)


@router.post("/providers", response_model=SSOProviderPublic, status_code=201)
async def create_provider(
    _admin: AdminUserDep,
    body: SSOProviderCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_provider_controller(session, body)


@router.get("/providers/{provider_id}", response_model=SSOProviderPublic)
async def get_provider(
    _admin: AdminUserDep,
    provider_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_provider_controller(session, provider_id)


@router.put("/providers/{provider_id}", response_model=SSOProviderPublic)
async def update_provider(
    _admin: AdminUserDep,
    provider_id: UUID,
    body: SSOProviderUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_provider_controller(session, provider_id, body)


@router.delete("/providers/{provider_id}", response_model=dict[str, bool])
async def delete_provider(
    _admin: AdminUserDep,
    provider_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await delete_provider_controller(session, provider_id)


@router.get("/sessions", response_model=list[SSOSessionPublic])
async def list_sessions(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    return await list_sessions_controller(session, skip=skip, limit=limit)


@router.delete("/sessions/{sso_session_id}", response_model=SSOSessionPublic)
async def terminate_session(
    _admin: AdminUserDep,
    sso_session_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await terminate_session_controller(session, sso_session_id)