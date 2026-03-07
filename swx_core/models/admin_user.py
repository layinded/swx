"""
Admin User Model
----------------
This module defines the AdminUser model for admin domain users.

Admin users are separate from regular users and have access to admin-only
endpoints and permissions. They do NOT have access to user domain endpoints.

This enforces clear separation between admin and user domains.
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import EmailStr
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


class AdminUserBase(Base):
    """
    Base model for admin user fields.

    Attributes:
        email (EmailStr): Unique email address.
        is_active (bool): Indicates if the admin account is active.
        full_name (Optional[str]): The admin's full name (optional).
    """

    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    full_name: Optional[str] = Field(default=None, max_length=255)


class AdminUser(AdminUserBase, table=True):
    """
    Database model representing an admin user.

    Admin users are separate from regular users and have access to admin-only
    endpoints. They authenticate separately and have their own token audience.

    Attributes:
        id (uuid.UUID): Unique admin user identifier.
        hashed_password (Optional[str]): Hashed password for authentication.
        auth_provider (str): The authentication provider (default: 'local').
        provider_id (Optional[str]): External authentication provider ID.
        createdAt (datetime): Timestamp when the admin user was created.
    """

    __tablename__ = "admin_user"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: Optional[str] = Field(default=None, max_length=255)
    auth_provider: str = Field(default="local", max_length=50)
    provider_id: Optional[str] = Field(default=None, unique=True, max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AdminUserCreate(SQLModel):
    """
    Schema for creating a new admin user.

    Attributes:
        email (EmailStr): Admin email (required).
        password (str): Password (8-40 characters).
        full_name (Optional[str]): Admin's full name (optional).
    """

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: Optional[str] = Field(default=None, max_length=255)
    # NOTE: Admin users are created by existing admins or system, not via registration


class AdminUserUpdate(SQLModel):
    """
    Schema for updating an existing admin user.

    Attributes:
        email (Optional[EmailStr]): New email (if updating).
        password (Optional[str]): New password (if updating).
        full_name (Optional[str]): Updated full name.
    """

    email: Optional[EmailStr] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, min_length=8, max_length=40)
    full_name: Optional[str] = Field(default=None, max_length=255)


class AdminUserPublic(AdminUserBase):
    """
    Schema for publicly visible admin user data.

    Attributes:
        id (uuid.UUID): Unique admin user identifier.
        auth_provider (str): Authentication provider.
    """

    id: uuid.UUID
    auth_provider: str

    class Config:
        from_attributes = True
