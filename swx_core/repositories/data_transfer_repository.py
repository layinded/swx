# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false, reportAttributeAccessIssue=false

from typing import Any
from uuid import UUID
from swx_core.utils.time import utc_now

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.data_export import DataExport
from swx_core.models.data_import import DataImport

def _apply_updates(instance: Any, updates: dict[str, Any]) -> Any:
    for field_name, value in updates.items():
        setattr(instance, field_name, value)
    return instance

# --- Data Export ---

async def create_export(session: AsyncSession, data: dict[str, Any]) -> DataExport:
    export = DataExport(**data)
    session.add(export)
    await session.commit()
    await session.refresh(export)
    return export

async def get_export_by_id(session: AsyncSession, export_id: UUID) -> DataExport | None:
    return await session.get(DataExport, export_id)

async def list_exports(session: AsyncSession, *, status: str | None = None, skip: int = 0, limit: int = 50) -> list[DataExport]:
    stmt = select(DataExport)
    if status is not None:
        stmt = stmt.where(DataExport.status == status)
    stmt = stmt.order_by(DataExport.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def update_export(session: AsyncSession, export_id: UUID, data: dict[str, Any]) -> DataExport | None:
    export = await get_export_by_id(session, export_id)
    if export is None:
        return None
    _apply_updates(export, {**data, "updated_at": utc_now()})
    session.add(export)
    await session.commit()
    await session.refresh(export)
    return export

async def get_exports_by_user(session: AsyncSession, user_id: UUID, *, skip: int = 0, limit: int = 50) -> list[DataExport]:
    stmt = select(DataExport).where(DataExport.user_id == user_id).order_by(DataExport.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def get_exports_by_status(session: AsyncSession, status: str, *, skip: int = 0, limit: int = 50) -> list[DataExport]:
    stmt = select(DataExport).where(DataExport.status == status).order_by(DataExport.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def get_export_count(session: AsyncSession, *, status: str | None = None) -> int:
    stmt = select(func.count()).select_from(DataExport)
    if status is not None:
        stmt = stmt.where(DataExport.status == status)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)

# --- Data Import ---

async def create_import(session: AsyncSession, data: dict[str, Any]) -> DataImport:
    imp = DataImport(**data)
    session.add(imp)
    await session.commit()
    await session.refresh(imp)
    return imp

async def get_import_by_id(session: AsyncSession, import_id: UUID) -> DataImport | None:
    return await session.get(DataImport, import_id)

async def list_imports(session: AsyncSession, *, status: str | None = None, skip: int = 0, limit: int = 50) -> list[DataImport]:
    stmt = select(DataImport)
    if status is not None:
        stmt = stmt.where(DataImport.status == status)
    stmt = stmt.order_by(DataImport.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def update_import(session: AsyncSession, import_id: UUID, data: dict[str, Any]) -> DataImport | None:
    imp = await get_import_by_id(session, import_id)
    if imp is None:
        return None
    _apply_updates(imp, {**data, "updated_at": utc_now()})
    session.add(imp)
    await session.commit()
    await session.refresh(imp)
    return imp

async def get_imports_by_user(session: AsyncSession, user_id: UUID, *, skip: int = 0, limit: int = 50) -> list[DataImport]:
    stmt = select(DataImport).where(DataImport.user_id == user_id).order_by(DataImport.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def get_imports_by_status(session: AsyncSession, status: str, *, skip: int = 0, limit: int = 50) -> list[DataImport]:
    stmt = select(DataImport).where(DataImport.status == status).order_by(DataImport.created_at.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def get_import_count(session: AsyncSession, *, status: str | None = None) -> int:
    stmt = select(func.count()).select_from(DataImport)
    if status is not None:
        stmt = stmt.where(DataImport.status == status)
    result = await session.execute(stmt)
    return int(result.scalar() or 0)