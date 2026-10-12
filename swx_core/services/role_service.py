from typing import List, Dict, Any
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.role import Role, RoleCreate, RoleUpdate
from swx_core.models.role_permission import RolePermission
from swx_core.repositories import role_repository, role_permission_repository, permission_repository
from swx_core.events.dispatcher import event_bus, Event
from swx_core.config.settings import settings


async def _invalidate_role_caches() -> None:
    """Invalidate role caches when role definitions change."""
    if settings.USER_CACHE_ENABLED:
        from swx_core.auth.auth_cache import invalidate_all_roles

        await invalidate_all_roles()


async def _invalidate_permission_caches() -> None:
    """Invalidate permission caches when role-permission mappings change."""
    if settings.USER_CACHE_ENABLED:
        from swx_core.auth.auth_cache import invalidate_all_permissions

        await invalidate_all_permissions()


async def list_roles_service(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Role]:
    return await role_repository.get_all_roles(session, skip, limit)


async def create_role_service(
    session: AsyncSession, 
    role_in: RoleCreate,
    event_context: Dict[str, Any] | None = None,
) -> Role:
    existing = await role_repository.get_role_by_name(session, role_in.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists",
        )
    role = await role_repository.create_role(session, role_in)
    
    payload = {
        "id": str(role.id),
        "data": {"name": role.name, "description": role.description},
    }
    if event_context is not None:
        payload["context"] = event_context
    
    await event_bus.emit(Event(
        name="role.created",
        payload=payload,
    ))
    
    return role


async def get_role_service(session: AsyncSession, role_id: UUID) -> Role:
    role = await role_repository.get_role_by_id(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return role


async def update_role_service(
    session: AsyncSession, 
    role_id: UUID, 
    role_in: RoleUpdate,
    event_context: Dict[str, Any] | None = None,
) -> Role:
    role = await get_role_service(session, role_id)
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update system roles",
        )
    old_values = {"name": role.name, "description": role.description}
    role = await role_repository.update_role(session, role, role_in)
    new_values = {"name": role.name, "description": role.description}
    
    await _invalidate_role_caches()
    
    await event_bus.emit(Event(
        name="role.updated",
        payload={
            "id": str(role.id),
            "old_values": old_values,
            "new_values": new_values,
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return role


async def delete_role_service(
    session: AsyncSession, 
    role_id: UUID,
    event_context: Dict[str, Any] | None = None,
) -> None:
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
    usage_count = result.scalar() or 0
    if usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete role assigned to users",
        )
        
    await role_repository.delete_role(session, role)
    
    await _invalidate_role_caches()
    
    await event_bus.emit(Event(
        name="role.deleted",
        payload={
            "id": str(role_id),
            "data": {"name": role.name},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))


# Role-Permission Management

async def assign_permission_to_role_service(
    session: AsyncSession, 
    role_id: UUID, 
    permission_id: UUID,
    event_context: Dict[str, Any] | None = None,
) -> RolePermission:
    await get_role_service(session, role_id)
    permission = await permission_repository.get_permission_by_id(session, permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    existing = await role_permission_repository.get_role_permission(session, role_id, permission_id)
    if existing:
        return existing

    rp = await role_permission_repository.assign_permission_to_role(session, role_id, permission_id)

    # Invalidate all cached permissions when role-permission mapping changes
    await _invalidate_permission_caches()

    await event_bus.emit(Event(
        name="role.permission_assigned",
        payload={
            "id": str(rp.id),
            "data": {"role_id": str(role_id), "permission_id": str(permission_id)},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return rp


async def remove_permission_from_role_service(
    session: AsyncSession, 
    role_id: UUID, 
    permission_id: UUID,
    event_context: Dict[str, Any] | None = None,
) -> None:
    rp = await role_permission_repository.get_role_permission(session, role_id, permission_id)
    if not rp:
        raise HTTPException(status_code=404, detail="Role-permission mapping not found")
    
    await role_permission_repository.remove_permission_from_role(session, rp)

    # Invalidate all cached permissions when role-permission mapping changes
    await _invalidate_permission_caches()
    
    await event_bus.emit(Event(
        name="role.permission_removed",
        payload={
            "id": str(rp.id),
            "data": {"role_id": str(role_id), "permission_id": str(permission_id)},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))


async def list_role_permissions_service(session: AsyncSession, role_id: UUID) -> List[RolePermission]:
    await get_role_service(session, role_id) # Validate existence
    return await role_permission_repository.list_role_permissions(session, role_id)
