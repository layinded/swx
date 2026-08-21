# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.admin.dependencies import AdminUserDep
from swx_core.controllers.feature_flag_controller import (
    create_flag_controller,
    delete_flag_controller,
    get_flag_controller,
    list_flags_controller,
    update_flag_controller,
    get_flag_evaluations_controller,
)
from swx_core.database.db import get_session
from swx_core.models.feature_flag import FeatureFlagCreate, FeatureFlagPublic, FeatureFlagUpdate
from swx_core.models.flag_evaluation import FlagEvaluationPublic

router = APIRouter(prefix="/admin/feature-flags", tags=["Admin - Feature Flags"])


@router.get("", response_model=list[FeatureFlagPublic])
async def list_flags(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    enabled: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_flags_controller(session, enabled=enabled, skip=skip, limit=limit)


@router.post("", response_model=FeatureFlagPublic, status_code=201)
async def create_flag(
    _admin: AdminUserDep,
    body: FeatureFlagCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_flag_controller(session, body)


@router.get("/{flag_id}", response_model=FeatureFlagPublic)
async def get_flag(
    _admin: AdminUserDep,
    flag_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_flag_controller(session, flag_id)


@router.put("/{flag_id}", response_model=FeatureFlagPublic)
async def update_flag(
    _admin: AdminUserDep,
    flag_id: UUID,
    body: FeatureFlagUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_flag_controller(session, flag_id, body)


@router.delete("/{flag_id}", response_model=FeatureFlagPublic)
async def delete_flag(
    _admin: AdminUserDep,
    flag_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await delete_flag_controller(session, flag_id)


@router.get("/{flag_id}/evaluations", response_model=list[FlagEvaluationPublic])
async def get_flag_evaluations(
    _admin: AdminUserDep,
    flag_id: UUID,
    session: AsyncSession = Depends(get_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await get_flag_evaluations_controller(session, flag_id, skip=skip, limit=limit)