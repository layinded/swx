from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.user_role import UserRole, UserRoleCreate
from swx_core.repositories import user_role_repository, user_repository, role_repository

async def assign_role_to_user_service(session: AsyncSession, assignment: UserRoleCreate) -> UserRole:
    user = await user_repository.get_user_by_id(session, assignment.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = await role_repository.get_role_by_id(session, assignment.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    existing = await user_role_repository.get_user_role_assignment(session, assignment)
    if existing:
        return existing
    
    return await user_role_repository.assign_role_to_user(session, assignment)

async def remove_role_from_user_service(session: AsyncSession, user_role_id: UUID) -> None:
    ur = await user_role_repository.get_user_role_by_id(session, user_role_id)
    if not ur:
        raise HTTPException(status_code=404, detail="User-role assignment not found")
    
    await user_role_repository.remove_role_from_user(session, ur)

async def list_user_roles_service(session: AsyncSession, user_id: UUID) -> List[UserRole]:
    return await user_role_repository.list_user_roles(session, user_id)
