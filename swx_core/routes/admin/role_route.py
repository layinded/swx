from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, status, Request

from swx_core.database.db import SessionDep
from swx_core.models.role import RoleCreate, RoleUpdate, RolePublic
from swx_core.models.role_permission import RolePermissionPublic
from swx_core.models.common import Message
from swx_core.auth.admin.dependencies import get_current_admin_user, AdminUserDep
from swx_core.controllers import role_controller
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome

router = APIRouter(
    prefix="/admin/role",
    tags=["admin-role"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/", response_model=list[RolePublic])
async def list_roles(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all roles."""
    return await role_controller.list_roles_controller(session, skip, limit)


@router.post("/", response_model=RolePublic, status_code=status.HTTP_201_CREATED)
async def create_role(
    session: SessionDep,
    role_in: RoleCreate,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Create a new role."""
    audit = get_audit_logger(session)
    try:
        role = await role_controller.create_role_controller(session, role_in)
        await audit.log_event(
            action="role.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            resource_id=str(role.id),
            outcome=AuditOutcome.SUCCESS,
            context=role_in.model_dump(),
            request=request
        )
        return role
    except Exception as e:
        await audit.log_event(
            action="role.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **role_in.model_dump()},
            request=request
        )
        raise e


@router.get("/{role_id}", response_model=RolePublic)
async def get_role(
    session: SessionDep,
    role_id: UUID,
) -> Any:
    """Get role by ID."""
    return await role_controller.get_role_controller(session, role_id)


@router.patch("/{role_id}", response_model=RolePublic)
async def update_role(
    session: SessionDep,
    role_id: UUID,
    role_in: RoleUpdate,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Update a role."""
    audit = get_audit_logger(session)
    try:
        role = await role_controller.update_role_controller(session, role_id, role_in)
        await audit.log_event(
            action="role.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            resource_id=str(role_id),
            outcome=AuditOutcome.SUCCESS,
            context=role_in.model_dump(),
            request=request
        )
        return role
    except Exception as e:
        await audit.log_event(
            action="role.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            resource_id=str(role_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **role_in.model_dump()},
            request=request
        )
        raise e


@router.delete("/{role_id}", response_model=Message)
async def delete_role(
    session: SessionDep,
    role_id: UUID,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Delete a role."""
    audit = get_audit_logger(session)
    try:
        await role_controller.delete_role_controller(session, role_id)
        await audit.log_event(
            action="role.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            resource_id=str(role_id),
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return Message(message="Role deleted successfully")
    except Exception as e:
        await audit.log_event(
            action="role.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            resource_id=str(role_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e


# Role-Permission Management

@router.post("/{role_id}/permission/{permission_id}", response_model=RolePermissionPublic)
async def assign_permission_to_role(
    session: SessionDep,
    role_id: UUID,
    permission_id: UUID,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Assign a permission to a role."""
    audit = get_audit_logger(session)
    try:
        res = await role_controller.assign_permission_to_role_controller(session, role_id, permission_id)
        await audit.log_event(
            action="role.permission.assign",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            resource_id=str(role_id),
            outcome=AuditOutcome.SUCCESS,
            context={"permission_id": str(permission_id)},
            request=request
        )
        return res
    except Exception as e:
        await audit.log_event(
            action="role.permission.assign",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            resource_id=str(role_id),
            outcome=AuditOutcome.FAILURE,
            context={"permission_id": str(permission_id), "error": str(e)},
            request=request
        )
        raise e


@router.delete("/{role_id}/permission/{permission_id}", response_model=Message)
async def remove_permission_from_role(
    session: SessionDep,
    role_id: UUID,
    permission_id: UUID,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Remove a permission from a role."""
    audit = get_audit_logger(session)
    try:
        await role_controller.remove_permission_from_role_controller(session, role_id, permission_id)
        await audit.log_event(
            action="role.permission.remove",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            resource_id=str(role_id),
            outcome=AuditOutcome.SUCCESS,
            context={"permission_id": str(permission_id)},
            request=request
        )
        return Message(message="Permission removed from role")
    except Exception as e:
        await audit.log_event(
            action="role.permission.remove",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="role",
            resource_id=str(role_id),
            outcome=AuditOutcome.FAILURE,
            context={"permission_id": str(permission_id), "error": str(e)},
            request=request
        )
        raise e


@router.get("/{role_id}/permission", response_model=list[RolePermissionPublic])
async def list_role_permissions(
    session: SessionDep,
    role_id: UUID,
) -> Any:
    """List all permissions for a role."""
    return await role_controller.list_role_permissions_controller(session, role_id)
