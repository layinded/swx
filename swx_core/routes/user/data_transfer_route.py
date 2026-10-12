# pyright: reportMissingTypeArgument=false

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers.data_transfer_controller import (
    create_export_controller,
    create_import_controller,
    get_export_controller,
    get_import_controller,
    get_user_exports_controller,
    get_user_imports_controller,
)
from swx_core.database.db import get_session
from swx_core.models.data_export import DataExportCreate, DataExportPublic
from swx_core.models.data_import import DataImportCreate, DataImportPublic

router = APIRouter(prefix="/data-transfer", tags=["User - Data Transfer"])


@router.post("/export", response_model=DataExportPublic, status_code=201)
async def request_export(
    user: UserDep,
    body: DataExportCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_export_controller(session, user.id, body)


@router.get("/exports", response_model=list[DataExportPublic])
async def list_my_exports(
    user: UserDep,
    session: AsyncSession = Depends(get_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await get_user_exports_controller(session, user.id, skip=skip, limit=limit)


@router.get("/exports/{export_id}", response_model=DataExportPublic)
async def get_my_export(
    user: UserDep,
    export_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_export_controller(session, export_id, user.id)


@router.post("/import", response_model=DataImportPublic, status_code=201)
async def request_import(
    user: UserDep,
    body: DataImportCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_import_controller(session, user.id, body)


@router.get("/imports", response_model=list[DataImportPublic])
async def list_my_imports(
    user: UserDep,
    session: AsyncSession = Depends(get_session),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await get_user_imports_controller(session, user.id, skip=skip, limit=limit)


@router.get("/imports/{import_id}", response_model=DataImportPublic)
async def get_my_import(
    user: UserDep,
    import_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_import_controller(session, import_id, user.id)