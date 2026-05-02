from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.role import Role, RoleCreate, RoleUpdate
from swx_core.models.role_permission import RolePermission
from swx_core.services import role_service

async def list_roles_controller(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Role]:
    return await role_service.list_roles_service(session, skip, limit)

async def create_role_controller(session: AsyncSession, role_in: RoleCreate) -> Role:
    return await role_service.create_role_service(session, role_in)

async def get_role_controller(session: AsyncSession, role_id: UUID) -> Role:
    return await role_service.get_role_service(session, role_id)

async def update_role_controller(session: AsyncSession, role_id: UUID, role_in: RoleUpdate) -> Role:
    return await role_service.update_role_service(session, role_id, role_in)

async def delete_role_controller(session: AsyncSession, role_id: UUID) -> None:
    return await role_service.delete_role_service(session, role_id)

# Role-Permission Management

async def assign_permission_to_role_controller(session: AsyncSession, role_id: UUID, permission_id: UUID) -> RolePermission:
    return await role_service.assign_permission_to_role_service(session, role_id, permission_id)

async def remove_permission_from_role_controller(session: AsyncSession, role_id: UUID, permission_id: UUID) -> None:
    return await role_service.remove_permission_from_role_service(session, role_id, permission_id)

async def list_role_permissions_controller(session: AsyncSession, role_id: UUID) -> List[RolePermission]:
    return await role_service.list_role_permissions_service(session, role_id)
