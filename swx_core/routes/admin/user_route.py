"""
Admin User Management Routes
----------------------------
This module defines API routes for **admin-level user management**, including:
- Retrieving all users.
- Fetching user details by ID.
- Creating new users.
- Updating user details.
- Deleting users.

Endpoints:
- `get_all_users()`: Retrieve a list of all users (Admin only).
- `get_user_by_id()`: Retrieve a user’s details by their ID (Admin only).
- `create_user()`: Create a new user (Admin only).
- `update_user()`: Update a user’s details (Admin only).
- `delete_user()`: Delete a user by ID (Admin only).
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, HTTPException

from swx_core.controllers.auth_controller import register_controller
from swx_core.controllers.user_controller import (
    get_all_users_controller,
    get_user_by_id_controller,
    update_user_controller,
    delete_user_controller,
)
from swx_core.database.db import SessionDep
from swx_core.models.common import Message
from swx_core.models.user import UserPublic, UsersPublic, UserCreate, UserUpdate
from swx_core.auth.admin.dependencies import get_current_admin_user, AdminUserDep
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome

# Define router with admin-level access dependency
# NOTE: Using AdminUserDep ensures only admin domain users can access these routes
router = APIRouter(
    prefix="/admin/user",
    dependencies=[Depends(get_current_admin_user)],  # ✅ Restrict to Admin domain users
)


@router.get("/", response_model=UsersPublic, operation_id="get_all_users")
async def get_all_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve a list of all users (Admin only).

    Args:
        session (SessionDep): The database session.
        skip (int): Number of records to skip (pagination).
        limit (int): Maximum number of users to return.

    Returns:
        UsersPublic: A list of users with a total count.

    Raises:
        HTTPException: If no users are found.
    """
    users = await get_all_users_controller(session, skip, limit)
    if not users:
        raise HTTPException(status_code=404, detail="No users found")
    return UsersPublic(data=users, count=len(users))


@router.get("/{user_id}", response_model=UserPublic, operation_id="get_user_by_id")
async def get_user_by_id(
    session: SessionDep,
    user_id: UUID,
    admin_user: AdminUserDep,  # Admin authentication
    request: Request = None,
) -> Any:
    """
    Retrieve details of a specific user by ID (Admin only).

    Args:
        session (SessionDep): The database session.
        user_id (UUID): The unique ID of the user.
        admin_user (AdminUserDep): The authenticated admin user (for authorization).
        request (Request, optional): The HTTP request object.

    Returns:
        UserPublic: The requested user's details.

    Raises:
        HTTPException: If the user is not found.
    """
    # NOTE: Controller manages User domain objects, admin_user is just for auth
    # get_user_by_id_service doesn't use current_user, so we can pass None
    user = await get_user_by_id_controller(session, str(user_id), None, request)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=UserPublic, operation_id="create_user")
async def create_user(
    session: SessionDep,
    user_in: UserCreate,
    request: Request,
    current_admin: AdminUserDep,
) -> Any:
    """
    Create a new user (Admin only).

    Args:
        session (SessionDep): The database session.
        user_in (UserCreate): The new user data.
        request (Request): The HTTP request object.

    Returns:
        UserPublic: The created user's details.

    Raises:
        HTTPException: If user creation fails.
    """
    audit = get_audit_logger(session)
    try:
        user = await register_controller(session, user_in, request)
        if not user:
            raise HTTPException(status_code=400, detail="User creation failed")
        
        await audit.log_event(
            action="user.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="user",
            resource_id=str(user.id),
            outcome=AuditOutcome.SUCCESS,
            context=user_in.model_dump(),
            request=request
        )
        return user
    except Exception as e:
        await audit.log_event(
            action="user.create",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="user",
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **user_in.model_dump()},
            request=request
        )
        raise e


@router.patch("/{user_id}", response_model=UserPublic, operation_id="update_user")
async def update_user(
    session: SessionDep,
    user_id: UUID,
    user_in: UserUpdate,
    admin_user: AdminUserDep,  # Admin authentication
    request: Request = None,
) -> Any:
    """
    Update a user's details (Admin only).

    Args:
        session (SessionDep): The database session.
        user_id (UUID): The unique ID of the user.
        user_in (UserUpdate): The updated user data.
        admin_user (AdminUserDep): The authenticated admin user (for authorization).
        request (Request, optional): The HTTP request object.

    Returns:
        UserPublic: The updated user details.

    Raises:
        HTTPException: If user update fails.
    """
    # NOTE: For admin, we update the target user (user_id), not the admin user
    # Fetch the target user first
    audit = get_audit_logger(session)
    from swx_core.repositories.user_repository import get_user_by_id
    target_user = await get_user_by_id(session, str(user_id))
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        user = await update_user_controller(session, user_in, target_user, request)
        if not user:
            raise HTTPException(status_code=400, detail="User update failed")
        
        await audit.log_event(
            action="user.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(admin_user.id),
            resource_type="user",
            resource_id=str(user_id),
            outcome=AuditOutcome.SUCCESS,
            context=user_in.model_dump(),
            request=request
        )
        return user
    except Exception as e:
        await audit.log_event(
            action="user.update",
            actor_type=ActorType.ADMIN,
            actor_id=str(admin_user.id),
            resource_type="user",
            resource_id=str(user_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e), **user_in.model_dump()},
            request=request
        )
        raise e


@router.delete("/{user_id}", response_model=Message, operation_id="delete_user")
async def delete_user(
    session: SessionDep,
    user_id: UUID,
    admin_user: AdminUserDep,  # Admin authentication
    request: Request = None,
) -> Message:
    """
    Delete a user by ID (Admin only).

    Args:
        session (SessionDep): The database session.
        user_id (UUID): The unique ID of the user to delete.
        admin_user (AdminUserDep): The authenticated admin user (for authorization).
        request (Request, optional): The HTTP request object.

    Returns:
        Message: A confirmation message upon successful deletion.

    Raises:
        HTTPException: If user deletion fails.
    """
    # NOTE: Controller manages User domain objects, admin_user is just for auth
    # Get the user to delete first
    audit = get_audit_logger(session)
    from swx_core.repositories.user_repository import get_user_by_id
    user_to_delete = await get_user_by_id(session, str(user_id))
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        success = await delete_user_controller(session, user_to_delete, request)
        if not success:
            raise HTTPException(status_code=400, detail="User deletion failed")
        
        await audit.log_event(
            action="user.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(admin_user.id),
            resource_type="user",
            resource_id=str(user_id),
            outcome=AuditOutcome.SUCCESS,
            request=request
        )
        return Message(message="User deleted successfully")
    except Exception as e:
        await audit.log_event(
            action="user.delete",
            actor_type=ActorType.ADMIN,
            actor_id=str(admin_user.id),
            resource_type="user",
            resource_id=str(user_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise e
