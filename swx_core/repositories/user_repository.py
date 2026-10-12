"""
User Repository
---------------
Database operations for user authentication, registration, and management.

All database queries live here (SWX Controller → Service → Repository pattern).

PII encryption (dual-write strategy):
    When PII_ENCRYPTION_ENABLED is True, every write to User.email or
    User.full_name also populates email_encrypted / full_name_encrypted,
    and every read decrypts from the encrypted column (falling back to
    plaintext when the encrypted column is NULL for gradual migration).
"""

from typing import Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.middleware.logging_middleware import logger
from swx_core.models.user import User, UserCreate, UserUpdate
from swx_core.security.password_security import verify_password, get_password_hash
from swx_core.services.compliance.pii_encryption_service import (
    encrypt_email,
    pii_encryption_enabled,
    should_encrypt_pii,
    encrypt_user_pii,
    decrypt_user_pii,
)
from swx_core.utils.time import utc_now


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
    """Retrieve a user by email, querying the encrypted column when PII encryption is enabled."""
    logger.debug(f"Looking up user by email")
    if should_encrypt_pii():
        encrypted_email = encrypt_email(email)
        statement = select(User).where(User.email_encrypted == encrypted_email)
    else:
        statement = select(User).where(User.email == email)

    result = await session.execute(statement)
    user_found = result.scalar_one_or_none()

    if user_found and pii_encryption_enabled():
        decrypt_user_pii(user_found)

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
            "is_superuser": False,
        },
    )
    encrypt_user_pii(new_user)
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


async def get_user_by_id(session: AsyncSession, user_id: str | UUID) -> User | None:
    """Retrieve a user by ID, decrypting PII when encryption is enabled."""
    statement = select(User).where(User.id == user_id)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    if user and pii_encryption_enabled():
        decrypt_user_pii(user)
    return user


async def get_all_users(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
    """Retrieve all users with optional pagination, decrypting PII when encryption is enabled."""
    statement = select(User).offset(skip).limit(limit)
    result = await session.execute(statement)
    users = list(result.scalars().all())
    if pii_encryption_enabled():
        for user in users:
            decrypt_user_pii(user)
    return users


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
        hashed_password = await get_password_hash(password)
        extra_data["hashed_password"] = hashed_password

    db_user.sqlmodel_update(user_data, update=extra_data)
    encrypt_user_pii(db_user)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def update_user_password(
    session: AsyncSession, user_id: str | UUID, current_password: str, new_password: str
) -> bool:
    db_user = await get_user_by_id(session=session, user_id=user_id)
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
    session: AsyncSession, email: str, user_info: dict[str, Any], provider: str
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
    encrypt_user_pii(new_user)

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


async def increment_failed_login_attempts(session: AsyncSession, user: User) -> None:
    """Increment the failed login attempt counter and persist."""
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    session.add(user)
    await session.commit()


async def lock_user_account(session: AsyncSession, user: User, locked_until: datetime) -> None:
    """Lock a user account by setting locked_until and persisting."""
    user.locked_until = locked_until
    session.add(user)
    await session.commit()


async def reset_login_attempts(session: AsyncSession, user: User) -> None:
    """Reset failed login attempts and clear account lock after successful login."""
    user.failed_login_attempts = 0
    user.locked_until = None
    session.add(user)
    await session.commit()


async def update_password_reset_timestamp(session: AsyncSession, user: User) -> None:
    """Update password_reset_requested_at to the current time for rate limiting."""
    user.password_reset_requested_at = utc_now()
    session.add(user)
    await session.commit()


async def update_password_hash(session: AsyncSession, user: User, hashed_password: str) -> None:
    """Update a user's hashed password."""
    user.hashed_password = hashed_password
    session.add(user)
    await session.commit()
