from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.user_role import UserRole, UserRoleCreate
from swx_core.services import user_role_service

async def assign_role_to_user_controller(session: AsyncSession, assignment: UserRoleCreate) -> UserRole:
    return await user_role_service.assign_role_to_user_service(session, assignment)

async def remove_role_from_user_controller(session: AsyncSession, user_role_id: UUID) -> None:
    return await user_role_service.remove_role_from_user_service(session, user_role_id)

async def list_user_roles_controller(session: AsyncSession, user_id: UUID) -> List[UserRole]:
    return await user_role_service.list_user_roles_service(session, user_id)
