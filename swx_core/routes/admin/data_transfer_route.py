# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.admin.dependencies import AdminUserDep
from swx_core.controllers.data_transfer_controller import (
    cancel_export_controller,
    cancel_import_controller,
    list_exports_controller,
    list_imports_controller,
    get_export_controller,
    get_import_controller,
)
from swx_core.database.db import get_session
from swx_core.models.data_export import DataExportPublic
from swx_core.models.data_import import DataImportPublic

router = APIRouter(prefix="/admin/data-transfer", tags=["Admin - Data Transfer"])


@router.get("/exports", response_model=list[DataExportPublic])
async def list_exports(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_exports_controller(session, status=status, skip=skip, limit=limit)


@router.get("/exports/{export_id}", response_model=DataExportPublic)
async def get_export(
    _admin: AdminUserDep,
    export_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_export_controller(session, export_id)


@router.post("/exports/{export_id}/cancel", response_model=DataExportPublic)
async def cancel_export(
    _admin: AdminUserDep,
    export_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await cancel_export_controller(session, export_id)


@router.get("/imports", response_model=list[DataImportPublic])
async def list_imports(
    _admin: AdminUserDep,
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await list_imports_controller(session, status=status, skip=skip, limit=limit)


@router.get("/imports/{import_id}", response_model=DataImportPublic)
async def get_import(
    _admin: AdminUserDep,
    import_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_import_controller(session, import_id)


@router.post("/imports/{import_id}/cancel", response_model=DataImportPublic)
async def cancel_import(
    _admin: AdminUserDep,
    import_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await cancel_import_controller(session, import_id)