# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.admin.dependencies import AdminUserDep
from swx_core.controllers.safety_controller import (
    create_filter_controller,
    delete_filter_controller,
    get_check_controller,
    get_filter_controller,
    list_checks_controller,
    list_filters_controller,
    update_filter_controller,
)
from swx_core.database.db import get_session
from swx_core.models.content_filter import ContentFilterCreate, ContentFilterPublic, ContentFilterUpdate
from swx_core.models.safety_check import SafetyCheckPublic

router = APIRouter(prefix="/admin/safety", tags=["Admin - Safety"])


@router.get("/filters", response_model=list[ContentFilterPublic])
async def list_filters(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    enabled: bool | None = Query(default=None),
    category: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    return await list_filters_controller(session, enabled=enabled, category=category, skip=skip, limit=limit)


@router.post("/filters", response_model=ContentFilterPublic, status_code=201)
async def create_filter(
    _admin: AdminUserDep,
    body: ContentFilterCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_filter_controller(session, body)


@router.get("/filters/{filter_id}", response_model=ContentFilterPublic)
async def get_filter(
    _admin: AdminUserDep,
    filter_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_filter_controller(session, filter_id)


@router.put("/filters/{filter_id}", response_model=ContentFilterPublic)
async def update_filter(
    _admin: AdminUserDep,
    filter_id: UUID,
    body: ContentFilterUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_filter_controller(session, filter_id, body)


@router.delete("/filters/{filter_id}", response_model=ContentFilterPublic)
async def delete_filter(
    _admin: AdminUserDep,
    filter_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await delete_filter_controller(session, filter_id)


@router.get("/checks", response_model=list[SafetyCheckPublic])
async def list_checks(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    overall_verdict: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    return await list_checks_controller(session, overall_verdict=overall_verdict, skip=skip, limit=limit)


@router.get("/checks/{check_id}", response_model=SafetyCheckPublic)
async def get_check(
    _admin: AdminUserDep,
    check_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_check_controller(session, check_id)