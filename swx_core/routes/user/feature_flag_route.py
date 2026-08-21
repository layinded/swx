# pyright: reportMissingTypeArgument=false

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers.feature_flag_controller import (
    evaluate_flag_controller,
    evaluate_flags_for_user_controller,
    list_flags_controller,
)
from swx_core.database.db import get_session
from swx_core.models.feature_flag import FeatureFlagPublic

router = APIRouter(prefix="/feature-flags", tags=["User - Feature Flags"])


@router.post("/evaluate")
async def evaluate_flags(
    user: UserDep,
    session: AsyncSession = Depends(get_session),
    context: dict[str, Any] | None = None,
):
    return await evaluate_flags_for_user_controller(session, user.id, context)


@router.get("", response_model=list[FeatureFlagPublic])
async def list_enabled_flags(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    return await list_flags_controller(session, enabled=True, skip=skip, limit=limit)


@router.get("/{flag_key}")
async def get_flag_by_key(
    user: UserDep,
    flag_key: str,
    session: AsyncSession = Depends(get_session),
    context: dict[str, Any] | None = None,
):
    return await evaluate_flag_controller(session, flag_key, user.id, context)