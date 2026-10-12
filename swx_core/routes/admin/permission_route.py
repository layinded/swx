from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, status, Request

from swx_core.database.db import SessionDep
from swx_core.models.permission import PermissionCreate, PermissionUpdate, PermissionPublic
from swx_core.models.common import Message
from swx_core.auth.admin.dependencies import get_current_admin_user, AdminUserDep
from swx_core.controllers import permission_controller
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome

router = APIRouter(
    prefix="/admin/permission",
    tags=["admin-permission"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/", response_model=list[PermissionPublic])
async def list_permissions(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all permissions."""
    return await permission_controller.list_permissions_controller(session, skip, limit)

@router.post("/", response_model=PermissionPublic, status_code=status.HTTP_201_CREATED)
async def create_permission(
    session: SessionDep,
    permission_in: PermissionCreate,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Create a new permission."""
    audit = get_audit_logger(session)
    try:
        permission = await permission_controller.create_permission_controller(session, permission_in)
        await audit.log_event(
            action="permission.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="permission",
            resource_id=str(permission.id),
            outcome=AuditOutcome.SUCCESS,
            context=permission_in.model_dump(),
            request=request
        )
        return permission
    except Exception as e:
        await audit.log_event(
            action="permission.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="permission",
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **permission_in.model_dump()},
            request=request
        )
        raise e

@router.get("/{permission_id}", response_model=PermissionPublic)
async def get_permission(
    session: SessionDep,
    permission_id: UUID,
) -> Any:
    """Get permission by ID."""
    return await permission_controller.get_permission_controller(session, permission_id)

@router.patch("/{permission_id}", response_model=PermissionPublic)
async def update_permission(
    session: SessionDep,
    permission_id: UUID,
    permission_in: PermissionUpdate,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Update a permission."""
    audit = get_audit_logger(session)
    try:
        permission = await permission_controller.update_permission_controller(session, permission_id, permission_in)
        await audit.log_event(
            action="permission.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="permission",
            resource_id=str(permission_id),
            outcome=AuditOutcome.SUCCESS,
            context=permission_in.model_dump(),
            request=request
        )
        return permission
    except Exception as e:
        await audit.log_event(
            action="permission.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="permission",
            resource_id=str(permission_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **permission_in.model_dump()},
            request=request
        )
        raise e

@router.delete("/{permission_id}", response_model=Message)
async def delete_permission(
    session: SessionDep,
    permission_id: UUID,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Delete a permission."""
    audit = get_audit_logger(session)
    try:
        await permission_controller.delete_permission_controller(session, permission_id)
        await audit.log_event(
            action="permission.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="permission",
            resource_id=str(permission_id),
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return Message(message="Permission deleted successfully")
    except Exception as e:
        await audit.log_event(
            action="permission.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="permission",
            resource_id=str(permission_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e
