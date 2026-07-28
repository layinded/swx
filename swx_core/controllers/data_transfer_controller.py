from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.data_export import DataExportCreate, DataExportPublic, DataExportUpdate
from swx_core.models.data_import import DataImportCreate, DataImportPublic, DataImportUpdate
from swx_core.services.data_transfer import data_export_service, data_import_service


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def create_export_controller(session: AsyncSession, user_id: UUID, data: DataExportCreate) -> DataExportPublic:
    return await data_export_service.create_export(session, user_id, data)


async def get_export_controller(session: AsyncSession, export_id: UUID, user_id: UUID | None = None) -> DataExportPublic:
    try:
        return await data_export_service.get_export(session, export_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_exports_controller(session: AsyncSession, status: str | None = None, skip: int = 0, limit: int = 50) -> list[DataExportPublic]:
    return await data_export_service.list_exports(session, status=status, skip=skip, limit=limit)


async def cancel_export_controller(session: AsyncSession, export_id: UUID) -> DataExportPublic:
    try:
        return await data_export_service.cancel_export(session, export_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def get_user_exports_controller(session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 50) -> list[DataExportPublic]:
    return await data_export_service.get_user_exports(session, user_id, skip=skip, limit=limit)


async def create_import_controller(session: AsyncSession, user_id: UUID, data: DataImportCreate) -> DataImportPublic:
    return await data_import_service.create_import(session, user_id, data)


async def get_import_controller(session: AsyncSession, import_id: UUID, user_id: UUID | None = None) -> DataImportPublic:
    try:
        return await data_import_service.get_import(session, import_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_imports_controller(session: AsyncSession, status: str | None = None, skip: int = 0, limit: int = 50) -> list[DataImportPublic]:
    return await data_import_service.list_imports(session, status=status, skip=skip, limit=limit)


async def cancel_import_controller(session: AsyncSession, import_id: UUID) -> DataImportPublic:
    try:
        return await data_import_service.cancel_import(session, import_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def get_user_imports_controller(session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 50) -> list[DataImportPublic]:
    return await data_import_service.get_user_imports(session, user_id, skip=skip, limit=limit)