# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.admin.dependencies import get_current_admin_user
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

router = APIRouter(prefix="/feature-flags", tags=["Admin - Feature Flags"])


@router.get("", response_model=list[FeatureFlagPublic])
async def list_flags(
    enabled: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await list_flags_controller(session, enabled=enabled, skip=skip, limit=limit)


@router.post("", response_model=FeatureFlagPublic, status_code=201)
async def create_flag(
    body: FeatureFlagCreate,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await create_flag_controller(session, body)


@router.get("/{flag_id}", response_model=FeatureFlagPublic)
async def get_flag(
    flag_id: UUID,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await get_flag_controller(session, flag_id)


@router.put("/{flag_id}", response_model=FeatureFlagPublic)
async def update_flag(
    flag_id: UUID,
    body: FeatureFlagUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await update_flag_controller(session, flag_id, body)


@router.delete("/{flag_id}", response_model=FeatureFlagPublic)
async def delete_flag(
    flag_id: UUID,
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await delete_flag_controller(session, flag_id)


@router.get("/{flag_id}/evaluations", response_model=list[FlagEvaluationPublic])
async def get_flag_evaluations(
    flag_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _admin: dict = Depends(get_current_admin_user),
):
    return await get_flag_evaluations_controller(session, flag_id, skip=skip, limit=limit)