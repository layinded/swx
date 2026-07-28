# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnusedCallResult=false

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.data_import import DataImportCreate, DataImportPublic, DataImportUpdate
from swx_core.repositories import data_transfer_repository


async def create_import(session: AsyncSession, user_id: UUID, data: DataImportCreate) -> DataImportPublic:
    import_data: dict[str, Any] = {**data.model_dump(exclude_unset=True), "user_id": user_id, "status": "pending"}
    imp = await data_transfer_repository.create_import(session, import_data)
    await event_bus.dispatch("data_transfer.import_created", payload={"import_id": str(imp.id), "user_id": str(user_id)})
    return DataImportPublic.model_validate(imp)


async def get_import(session: AsyncSession, import_id: UUID, user_id: UUID | None = None) -> DataImportPublic:
    imp = await data_transfer_repository.get_import_by_id(session, import_id)
    if imp is None:
        raise ValueError("Import not found")
    if user_id is not None and imp.user_id != user_id:
        raise PermissionError("Import access denied")
    return DataImportPublic.model_validate(imp)


async def list_imports(session: AsyncSession, status: str | None = None, skip: int = 0, limit: int = 50) -> list[DataImportPublic]:
    imports = await data_transfer_repository.list_imports(session, status=status, skip=skip, limit=limit)
    return [DataImportPublic.model_validate(i) for i in imports]


async def update_import(session: AsyncSession, import_id: UUID, data: DataImportUpdate) -> DataImportPublic:
    imp = await data_transfer_repository.get_import_by_id(session, import_id)
    if imp is None:
        raise ValueError("Import not found")
    updated = await data_transfer_repository.update_import(session, import_id, data.model_dump(exclude_unset=True))
    await event_bus.dispatch("data_transfer.import_updated", payload={"import_id": str(import_id)})
    return DataImportPublic.model_validate(updated or imp)


async def cancel_import(session: AsyncSession, import_id: UUID) -> DataImportPublic:
    imp = await data_transfer_repository.get_import_by_id(session, import_id)
    if imp is None:
        raise ValueError("Import not found")
    updated = await data_transfer_repository.update_import(session, import_id, {"status": "cancelled"})
    await event_bus.dispatch("data_transfer.import_cancelled", payload={"import_id": str(import_id)})
    return DataImportPublic.model_validate(updated or imp)


async def get_user_imports(session: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 50) -> list[DataImportPublic]:
    imports = await data_transfer_repository.get_imports_by_user(session, user_id, skip=skip, limit=limit)
    return [DataImportPublic.model_validate(i) for i in imports]