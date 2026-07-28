# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.data_export import DataExportCreate, DataExportPublic, DataExportUpdate
from swx_core.repositories import data_transfer_repository


async def create_export(session: AsyncSession, user_id: UUID, data: DataExportCreate) -> DataExportPublic:
    export_data: dict[str, Any] = {**data.model_dump(exclude_unset=True), "user_id": user_id, "status": "pending"}
    export = await data_transfer_repository.create_export(session, export_data)
    await event_bus.dispatch("data_transfer.export_created", payload={"export_id": str(export.id), "user_id": str(user_id)})
    return DataExportPublic.model_validate(export)


async def get_export(session: AsyncSession, export_id: UUID, user_id: UUID | None = None) -> DataExportPublic:
    export = await data_transfer_repository.get_export_by_id(session, export_id)
    if export is None:
        raise ValueError("Export not found")
    if user_id is not None and export.user_id != user_id:
        raise PermissionError("Export access denied")
    return DataExportPublic.model_validate(export)


async def list_exports(session: AsyncSession, status: str | None = None, skip: int = 0, limit: int = 50) -> list[DataExportPublic]:
    exports = await data_transfer_repository.list_exports(session, status=status, skip=skip, limit=limit)
    return [DataExportPublic.model_validate(e) for e in exports]


async def update_export(session: AsyncSession, export_id: UUID, data: DataExportUpdate) -> DataExportPublic:
    export = await data_transfer_repository.get_export_by_id(session, export_id)
    if export is None:
        raise ValueError("Export not found")
    updated = await data_transfer_repository.update_export(session, export_id, data.model_dump(exclude_unset=True))
    await event_bus.dispatch("data_transfer.export_updated", payload={"export_id": str(export_id)})
    return DataExportPublic.model_validate(updated or export)


async def cancel_export(session: AsyncSession, export_id: UUID) -> DataExportPublic:
    export = await data_transfer_repository.get_export_by_id(session, export_id)
    if export is None:
        raise ValueError("Export not found")
    updated = await data_transfer_repository.update_export(session, export_id, {"status": "cancelled"})
    await event_bus.dispatch("data_transfer.export_cancelled", payload={"export_id": str(export_id)})
    return DataExportPublic.model_validate(updated or export)


async def get_user_exports(session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 50) -> list[DataExportPublic]:
    exports = await data_transfer_repository.get_exports_by_user(session, user_id, skip=skip, limit=limit)
    return [DataExportPublic.model_validate(e) for e in exports]