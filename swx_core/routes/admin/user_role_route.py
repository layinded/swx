from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, status

from swx_core.database.db import SessionDep
from swx_core.models.user_role import UserRoleCreate, UserRolePublic
from swx_core.models.common import Message
from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import user_role_controller

router = APIRouter(
    prefix="/admin/user-role",
    tags=["admin-user-role"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.post("/", response_model=UserRolePublic, status_code=status.HTTP_201_CREATED)
async def assign_role_to_user(
    session: SessionDep,
    assignment: UserRoleCreate,
) -> Any:
    """Assign a role to a user, optionally scoped to a team or resource."""
    return await user_role_controller.assign_role_to_user_controller(session, assignment)

@router.delete("/{user_role_id}", response_model=Message)
async def remove_role_from_user(
    session: SessionDep,
    user_role_id: UUID,
) -> Any:
    """Remove a role assignment from a user."""
    await user_role_controller.remove_role_from_user_controller(session, user_role_id)
    return Message(message="Role removed from user")

@router.get("/user/{user_id}", response_model=list[UserRolePublic])
async def list_user_roles(
    session: SessionDep,
    user_id: UUID,
) -> Any:
    """List all roles assigned to a specific user."""
    return await user_role_controller.list_user_roles_controller(session, user_id)
