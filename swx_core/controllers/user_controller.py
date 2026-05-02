"""
User Controller
----------------------
This module serves as the controller layer for user-related endpoints.

Features:
- Handles user profile management.
- Retrieves user information.
- Updates user profile and password.
- Deletes user accounts.

Methods:
- `update_user_controller()`: Updates the user's profile information.
- `get_current_user_controller()`: Returns the authenticated user's details.
- `get_user_by_id_controller()`: Retrieves user details by user ID.
- `get_all_users_controller()`: Fetches a paginated list of all users.
- `update_password_controller()`: Updates the user's password.
- `delete_user_controller()`: Deletes a user's account.
"""

from fastapi import HTTPException, Request

from swx_core.models.user import User, UserCreate, UserUpdate, UserUpdatePassword
from swx_core.services.user_service import (
    update_user_profile_service,
    get_user_by_id_service,
    update_password_service,
    delete_user_service,
    get_all_users_service,
)


async def update_user_controller(
    session, user_in: UserUpdate, current_user: User, request: Request
):
    """
    Updates the authenticated user's profile information.

    Args:
        session: The database session.
        user_in (UserUpdate): The user profile update data.
        current_user (User): The currently authenticated user.
        request (Request): The HTTP request object.

    Returns:
        User: The updated user profile.
    """
    return await update_user_profile_service(session, user_in, current_user, request)


def get_current_user_controller(current_user: User):
    """
    Retrieves the authenticated user's details.

    Args:
        current_user (User): The currently authenticated user.

    Returns:
        User: The authenticated user's details.
    """
    return current_user


async def get_user_by_id_controller(
    session, user_id, current_user: User | None, request: Request
):
    """
    Retrieves user details by their unique ID.

    Args:
        session: The database session.
        user_id (str): The unique identifier of the user.
        current_user (User | None): The currently authenticated user (optional, for access control).
        request (Request): The HTTP request object.

    Returns:
        User: The requested user object.

    Raises:
        HTTPException: If the user is not found.
    """
    return await get_user_by_id_service(session, user_id, current_user, request)


async def get_all_users_controller(session, skip: int, limit: int):
    """
    Retrieves a paginated list of all users.

    Args:
        session: The database session.
        skip (int): The number of users to skip.
        limit (int): The maximum number of users to retrieve.

    Returns:
        list[User]: A list of user objects.

    Raises:
        HTTPException: If no users are found.
    """
    users = await get_all_users_service(session, skip, limit)
    if not users:
        raise HTTPException(status_code=404, detail="No users found")
    return users


async def update_password_controller(
    session, current_user: User, body: UserUpdatePassword, request: Request
):
    """
    Updates the authenticated user's password.

    Args:
        session: The database session.
        current_user (User): The currently authenticated user.
        body (UserUpdatePassword): The password update request.
        request (Request): The HTTP request object.

    Returns:
        dict: A success message confirming password update.
    """
    return await update_password_service(session, current_user, body, request)


async def delete_user_controller(session, current_user: User, request: Request):
    """
    Deletes the authenticated user's account.

    Args:
        session: The database session.
        current_user (User): The currently authenticated user.
        request (Request): The HTTP request object.

    Returns:
        dict: A success message confirming account deletion.
    """
    return delete_user_service(session, current_user, request)
