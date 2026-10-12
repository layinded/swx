from typing import List, Dict, Any
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from swx_core.models.user_role import UserRole, UserRoleCreate
from swx_core.repositories import user_role_repository, user_repository, role_repository
from swx_core.events.dispatcher import event_bus, Event
from swx_core.auth.auth_cache import invalidate_user_permissions, invalidate_user_roles
from swx_core.services.audit_logger import AuditLogger, ActorType, AuditOutcome, AuditAction


async def _invalidate_user_assignment_caches(user_id: UUID) -> None:
    """Invalidate cached permissions and roles after role assignment changes."""
    await invalidate_user_permissions(user_id)
    await invalidate_user_roles(user_id)


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

    # Invalidate cached permissions and roles after role assignment
    await _invalidate_user_assignment_caches(assignment.user_id)

    await event_bus.emit(Event(
        name="user_role.assigned",
        payload={
            "id": str(user_role.id),
            "data": {"user_id": str(assignment.user_id), "role_id": str(assignment.role_id)},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.RBAC_ROLE_ASSIGNED,
        actor_type=ActorType.ADMIN,
        resource_type="user_role",
        resource_id=str(user_role.id),
        outcome=AuditOutcome.SUCCESS,
        context={"user_id": str(assignment.user_id), "role_id": str(assignment.role_id)},
    )

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

    # Invalidate cached permissions and roles after role removal
    await _invalidate_user_assignment_caches(ur.user_id)
    
    await event_bus.emit(Event(
        name="user_role.removed",
        payload={
            "id": str(user_role_id),
            "data": {"user_id": user_id, "role_id": role_id},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.RBAC_ROLE_REMOVED,
        actor_type=ActorType.ADMIN,
        resource_type="user_role",
        resource_id=str(user_role_id),
        outcome=AuditOutcome.SUCCESS,
        context={"user_id": user_id, "role_id": role_id},
    )


async def list_user_roles_service(session: AsyncSession, user_id: UUID) -> List[UserRole]:
    return await user_role_repository.list_user_roles(session, user_id)
