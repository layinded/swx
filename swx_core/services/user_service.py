"""
User Profile Service
----------------------
This module provides user profile management services, including:
- Profile updates
- Password updates
- User retrieval
- User deletion

Methods:
- `update_user_profile_service()`: Updates a user's profile information.
- `get_all_users_service()`: Retrieves a paginated list of all users.
- `get_user_by_id_service()`: Fetches user details by user ID.
- `update_password_service()`: Updates a user's password after verification.
- `delete_user_service()`: Deletes a user's account.

Events Emitted:
- user.updated: Emitted when user profile is updated
- user.password_changed: Emitted when password is changed
- user.deleted: Emitted when user account is deleted
"""

from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.user import User, UserUpdate
from swx_core.repositories.user_repository import (
    update_user,
    get_user_by_id,
    update_user_password,
    delete_user,
    get_all_users,
)
from swx_core.utils.language_helper import translate
from swx_core.events.dispatcher import EventBus, Event


async def update_user_profile_service(
    session: AsyncSession, 
    user_in: UserUpdate, 
    current_user: User, 
    request: Request,
    event_context: Dict[str, Any] | None = None,
) -> User:
    """
    Updates the profile information of the current user.

    Args:
        session (AsyncSession): The database session.
        user_in (UserUpdate): The updated user data.
        current_user (User): The currently authenticated user.
        request (Request): The HTTP request object.
        event_context (Dict[str, Any] | None): Additional context for user.updated event.

    Returns:
        User: The updated user profile.
    """
    old_values = {"email": current_user.email, "full_name": current_user.full_name}
    updated_user = await update_user(session=session, db_user=current_user, user_in=user_in)
    new_values = {"email": updated_user.email, "full_name": updated_user.full_name}
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="user.updated",
        payload={
            "id": str(updated_user.id),
            "old_values": old_values,
            "new_values": new_values,
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return updated_user


async def get_all_users_service(session: AsyncSession, skip: int, limit: int) -> List[User]:
    """
    Retrieves a paginated list of all users.

    Args:
        session (AsyncSession): The database session.
        skip (int): The number of users to skip.
        limit (int): The maximum number of users to retrieve.

    Returns:
        List[User]: A list of user objects.
    """
    users = await get_all_users(session, skip, limit)
    return users


async def get_user_by_id_service(session: AsyncSession, user_id: str | UUID, current_user: Optional[User] = None, request: Optional[Request] = None) -> User:
    """
    Retrieves user details by their unique ID.

    Args:
        session (AsyncSession): The database session.
        user_id (str | UUID): The unique identifier of the user.
        current_user (Optional[User]): The currently authenticated user (for access control checks).
        request (Optional[Request]): The HTTP request object.

    Returns:
        User: The requested user object.

    Raises:
        HTTPException: If the user is not found.
    """
    user_obj = await get_user_by_id(session, user_id)
    if not user_obj:
        raise HTTPException(
            status_code=404, detail=translate(request, "user_not_found")
        )
    return user_obj


async def update_password_service(
    session: AsyncSession, 
    current_user: User, 
    body: Any, 
    request: Request,
    event_context: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    """
    Updates the password for the authenticated user after verification.

    Args:
        session (AsyncSession): The database session.
        current_user (User): The currently authenticated user (User object).
        body (Any): The password update request containing the old and new password.
        request (Request): The HTTP request object.
        event_context (Dict[str, Any] | None): Additional context for user.password_changed event.

    Returns:
        Dict[str, str]: A success message confirming password update.

    Raises:
        HTTPException: If the password update fails.
    """
    updated = await update_user_password(
        session, str(current_user.id), body.current_password, body.new_password
    )
    if not updated:
        raise HTTPException(
            status_code=400, detail=translate(request, "password_update_failed")
        )
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="user.password_changed",
        payload={
            "id": str(current_user.id),
            "data": {"email": current_user.email},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return {"message": translate(request, "password_updated_successfully") or "Password updated successfully"}


async def delete_user_service(
    session: AsyncSession, 
    current_user: User, 
    request: Request,
    event_context: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    """
    Deletes the authenticated user's account.

    Args:
        session (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
        request (Request): The HTTP request object.
        event_context (Dict[str, Any] | None): Additional context for user.deleted event.

    Returns:
        Dict[str, str]: A success message confirming account deletion.

    Raises:
        HTTPException: If the user deletion fails.
    """
    user_id = str(current_user.id)
    user_email = current_user.email
    
    deleted = await delete_user(session, current_user)
    if not deleted:
        raise HTTPException(
            status_code=400, detail=translate(request, "user_deletion_failed")
        )
    
    event_bus = EventBus()
    await event_bus.emit(Event(
        name="user.deleted",
        payload={
            "id": user_id,
            "data": {"email": user_email},
            **({"context": event_context} if event_context is not None else {}),
        },
    ))
    
    return {"message": translate(request, "user_deleted_successfully") or "User deleted successfully"}
