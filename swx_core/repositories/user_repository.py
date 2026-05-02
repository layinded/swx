"""
User Service
------------
This module provides user authentication, registration, and management services.

Features:
- Supports local and social login authentication.
- Provides user management functionalities (CRUD operations).
- Implements password hashing and verification.

Methods:
- `authenticate_user()`: Authenticate a user using email and password.
- `get_user_by_email()`: Retrieve a user by their email address.
- `create_user()`: Create a new user (local or social).
- `get_user_by_id()`: Retrieve a user by their unique ID.
- `get_all_users()`: Retrieve all users with optional pagination.
- `update_user()`: Update user information, including password if applicable.
- `update_user_password()`: Update user password after verification.
- `delete_user()`: Delete a user from the system.
- `create_social_user()`: Create a new user from a social login provider.
"""

from typing import Any, List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.middleware.logging_middleware import logger
from swx_core.models.user import User, UserCreate, UserUpdate, UserUpdatePassword
from swx_core.security.password_security import verify_password, get_password_hash


async def authenticate_user(*, session: AsyncSession, email: str, password: str) -> User | None:
    """
    Authenticate a user using email and password (for local accounts only).

    Args:
        session (AsyncSession): The database session.
        email (str): The user's email address.
        password (str): The provided password.

    Returns:
        User | None: The authenticated user if successful, otherwise None.
    """
    db_user = await get_user_by_email(session=session, email=email)
    if not db_user:
        logger.debug(f"Authentication failed: no user found for email {email}")
        return None

    if db_user.auth_provider == "local":
        if not db_user.hashed_password or not await verify_password(
            password, db_user.hashed_password
        ):
            logger.debug(f"Authentication failed: incorrect password for email {email}")
            return None

    logger.debug(f"User authenticated: {db_user}")
    return db_user


async def get_user_by_email(*, session: AsyncSession, email: str) -> User | None:
    """
    Retrieve a user by email (for local and social logins).

    Args:
        session (AsyncSession): The database session.
        email (str): The user's email address.

    Returns:
        User | None: The retrieved user if found, otherwise None.
    """
    logger.debug(f"Looking up user by email: {email}")
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    user_found = result.scalar_one_or_none()
    if user_found:
        logger.debug(f"Found user: {user_found}")
    else:
        logger.debug("No user found.")
    return user_found


async def create_user(
    *,
    session: AsyncSession,
    user_create: UserCreate,
    auth_provider: str = "local",
    provider_id: str | None = None,
) -> User:
    """
    Create a new user with support for both local and social logins.

    Args:
        session (AsyncSession): The database session.
        user_create (UserCreate): The user creation data.
        auth_provider (str): The authentication provider (e.g., "local", "google").
        provider_id (str | None): The provider-specific user ID.

    Returns:
        User: The newly created user.
    """
    hashed_password = (
        await get_password_hash(user_create.password) if auth_provider == "local" else None
    )

    new_user = User.model_validate(
        user_create,
        update={
            "hashed_password": hashed_password,
            "auth_provider": auth_provider,
            "provider_id": provider_id,
            "is_superuser": False,  # Security: Never allow superuser creation via registration
        },
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


async def get_user_by_id(session: AsyncSession, user_id: str | UUID) -> User | None:
    """
    Retrieve a user by their unique ID.

    Args:
        session (AsyncSession): The database session.
        user_id (str | UUID): The user's unique identifier.

    Returns:
        User | None: The retrieved user if found, otherwise None.
    """
    statement = select(User).where(User.id == user_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_all_users(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    """
    Retrieve all users with optional pagination.

    Args:
        session (AsyncSession): The database session.
        skip (int): Number of users to skip for pagination.
        limit (int): Maximum number of users to return.

    Returns:
        List[User]: A list of user records.
    """
    statement = select(User).offset(skip).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def update_user(*, session: AsyncSession, db_user: User, user_in: UserUpdate) -> User:
    """
    Update user details, including password hashing if applicable.

    Args:
        session (AsyncSession): The database session.
        db_user (User): The existing user to update.
        user_in (UserUpdate): The new user data.

    Returns:
        User: The updated user record.
    """
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}

    if "password" in user_data and db_user.auth_provider == "local":
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password

    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def update_user_password(
    session: AsyncSession, user_id: str | UUID, current_password: str, new_password: str
) -> bool:
    """
    Update user password after verifying the current password.

    Args:
        session (AsyncSession): The database session.
        user_id (str | UUID): The user's ID (UUID).
        current_password (str): The user's current password.
        new_password (str): The new password to be set.

    Returns:
        bool: True if the password was updated successfully, otherwise False.
    """
    db_user = await session.get(User, user_id)
    if not db_user:
        return False
    if not await authenticate_user(
        session=session,
        email=db_user.email,
        password=current_password,
    ):
        return False

    await update_user(
        session=session, db_user=db_user, user_in=UserUpdate(password=new_password)
    )
    return True


async def delete_user(session: AsyncSession, current_user: User) -> bool:
    """
    Delete a user from the system.

    Args:
        session (AsyncSession): The database session.
        current_user (User): The user to be deleted.

    Returns:
        bool: True if the deletion was successful, False otherwise.
    """
    try:
        await session.delete(current_user)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        await session.rollback()
        return False


async def create_social_user(
    session: AsyncSession, email: str, user_info: dict, provider: str
) -> User:
    """
    Create a new user from a social login (Google, Facebook, GitHub).

    Args:
        session (AsyncSession): The database session.
        email (str): The user's email address.
        user_info (dict): The social provider's user information.
        provider (str): The authentication provider (e.g., "google", "facebook").

    Returns:
        User: The newly created or existing user.
    """
    db_user = await get_user_by_email(session=session, email=email)

    if db_user:
        return db_user

    if provider == "google":
        provider_id = user_info.get("sub")  # Google `sub`
    elif provider == "facebook":
        provider_id = user_info.get("id")  # Facebook `id`
    else:
        provider_id = None

    if not provider_id:
        raise ValueError(f"Missing provider ID for {provider} login")

    new_user = User(
        email=email,
        full_name=user_info.get("name"),
        provider_id=provider_id,
        auth_provider=provider,
        is_active=True,
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user
