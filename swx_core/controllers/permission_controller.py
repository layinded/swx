from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.permission import Permission, PermissionCreate, PermissionUpdate
from swx_core.services import permission_service

async def list_permissions_controller(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Permission]:
    return await permission_service.list_permissions_service(session, skip, limit)

async def create_permission_controller(session: AsyncSession, permission_in: PermissionCreate) -> Permission:
    return await permission_service.create_permission_service(session, permission_in)

async def get_permission_controller(session: AsyncSession, permission_id: UUID) -> Permission:
    return await permission_service.get_permission_service(session, permission_id)

async def update_permission_controller(session: AsyncSession, permission_id: UUID, permission_in: PermissionUpdate) -> Permission:
    return await permission_service.update_permission_service(session, permission_id, permission_in)

async def delete_permission_controller(session: AsyncSession, permission_id: UUID) -> None:
    return await permission_service.delete_permission_service(session, permission_id)
