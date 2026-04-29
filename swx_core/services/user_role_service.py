from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.user_role import UserRole, UserRoleCreate
from swx_core.repositories import user_role_repository, user_repository, role_repository
from swx_core.events.dispatcher import EventBus, Event


async def assign_role_to_user_service(
    session: AsyncSession, 
    assignment: UserRoleCreate,
    event_context: Dict[str, Any] | None = None,
) -> UserRole:
    user = await user_repository.get_user_by_id(session, assignment.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = await role_repository.get_role_by_id(session, assignment.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    existing = await user_role_repository.get_user_role_assignment(session, assignment)
    if existing:
        return existing
    
    user_role = await user_role_repository.assign_role_to_user(session, assignment)
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="user_role.assigned",
        payload={
            "id": str(user_role.id),
            "data": {"user_id": str(assignment.user_id), "role_id": str(assignment.role_id)},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return user_role


async def remove_role_from_user_service(
    session: AsyncSession, 
    user_role_id: UUID,
    event_context: Dict[str, Any] | None = None,
) -> None:
    ur = await user_role_repository.get_user_role_by_id(session, user_role_id)
    if not ur:
        raise HTTPException(status_code=404, detail="User-role assignment not found")
    
    user_id = str(ur.user_id)
    role_id = str(ur.role_id)
    
    await user_role_repository.remove_role_from_user(session, ur)
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="user_role.removed",
        payload={
            "id": str(user_role_id),
            "data": {"user_id": user_id, "role_id": role_id},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))


async def list_user_roles_service(session: AsyncSession, user_id: UUID) -> List[UserRole]:
    return await user_role_repository.list_user_roles(session, user_id)
