from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import HTTPException, status
from swx_core.models.permission import Permission, PermissionCreate, PermissionUpdate
from swx_core.repositories import permission_repository
from swx_core.events.dispatcher import EventBus, Event
from sqlalchemy.ext.asyncio import AsyncSession


async def list_permissions_service(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Permission]:
    return await permission_repository.get_all_permissions(session, skip, limit)


async def create_permission_service(
    session: AsyncSession, 
    permission_in: PermissionCreate,
    event_context: Dict[str, Any] | None = None,
) -> Permission:
    existing = await permission_repository.get_permission_by_name(session, permission_in.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission with this name already exists",
        )
    permission = await permission_repository.create_permission(session, permission_in)
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="permission.created",
        payload={
            "id": str(permission.id),
            "data": {"name": permission.name, "description": permission.description},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return permission


async def get_permission_service(session: AsyncSession, permission_id: UUID) -> Permission:
    permission = await permission_repository.get_permission_by_id(session, permission_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )
    return permission


async def update_permission_service(
    session: AsyncSession, 
    permission_id: UUID, 
    permission_in: PermissionUpdate,
    event_context: Dict[str, Any] | None = None,
) -> Permission:
    permission = await get_permission_service(session, permission_id)
    old_values = {"name": permission.name, "description": permission.description}
    permission = await permission_repository.update_permission(session, permission, permission_in)
    new_values = {"name": permission.name, "description": permission.description}
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="permission.updated",
        payload={
            "id": str(permission.id),
            "old_values": old_values,
            "new_values": new_values,
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return permission


async def delete_permission_service(
    session: AsyncSession, 
    permission_id: UUID,
    event_context: Dict[str, Any] | None = None,
) -> None:
    permission = await get_permission_service(session, permission_id)
    
    # Check if used in roles (This check could also be in repository, but service is fine)
    from sqlmodel import select, func
    from swx_core.models.role_permission import RolePermission
    usage_statement = select(func.count()).select_from(RolePermission).where(RolePermission.permission_id == permission_id)
    result = await session.execute(usage_statement)
    usage_count = result.scalar()
    if usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete permission assigned to roles",
        )
        
    await permission_repository.delete_permission(session, permission)
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="permission.deleted",
        payload={
            "id": str(permission_id),
            "data": {"name": permission.name},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
