from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.role import Role, RoleCreate, RoleUpdate
from swx_core.models.role_permission import RolePermission
from swx_core.repositories import role_repository, role_permission_repository, permission_repository

async def list_roles_service(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Role]:
    return await role_repository.get_all_roles(session, skip, limit)

async def create_role_service(session: AsyncSession, role_in: RoleCreate) -> Role:
    existing = await role_repository.get_role_by_name(session, role_in.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists",
        )
    return await role_repository.create_role(session, role_in)

async def get_role_service(session: AsyncSession, role_id: UUID) -> Role:
    role = await role_repository.get_role_by_id(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return role

async def update_role_service(session: AsyncSession, role_id: UUID, role_in: RoleUpdate) -> Role:
    role = await get_role_service(session, role_id)
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update system roles",
        )
    return await role_repository.update_role(session, role, role_in)

async def delete_role_service(session: AsyncSession, role_id: UUID) -> None:
    role = await get_role_service(session, role_id)
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system roles",
        )
    
    # Check if assigned to users
    from sqlmodel import select, func
    from swx_core.models.user_role import UserRole
    usage_statement = select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
    result = await session.execute(usage_statement)
    usage_count = result.scalar()
    if usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete role assigned to users",
        )
        
    await role_repository.delete_role(session, role)

# Role-Permission Management

async def assign_permission_to_role_service(session: AsyncSession, role_id: UUID, permission_id: UUID) -> RolePermission:
    role = await get_role_service(session, role_id)
    permission = await permission_repository.get_permission_by_id(session, permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    existing = await role_permission_repository.get_role_permission(session, role_id, permission_id)
    if existing:
        return existing

    return await role_permission_repository.assign_permission_to_role(session, role_id, permission_id)

async def remove_permission_from_role_service(session: AsyncSession, role_id: UUID, permission_id: UUID) -> None:
    rp = await role_permission_repository.get_role_permission(session, role_id, permission_id)
    if not rp:
        raise HTTPException(status_code=404, detail="Role-permission mapping not found")
    
    await role_permission_repository.remove_permission_from_role(session, rp)

async def list_role_permissions_service(session: AsyncSession, role_id: UUID) -> List[RolePermission]:
    await get_role_service(session, role_id) # Validate existence
    return await role_permission_repository.list_role_permissions(session, role_id)
