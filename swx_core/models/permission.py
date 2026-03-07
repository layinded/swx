"""
Permission Model
---------------
This module defines the Permission model for fine-grained access control.

Permissions are atomic actions that can be performed on resources.
Examples: "user:read", "user:write", "article:delete", "team:manage"

This is a permission-first RBAC system where:
- Permissions are explicit strings
- Roles are collections of permissions
- Users have roles, which grant permissions
"""

import uuid
from typing import Optional
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


class PermissionBase(Base):
    """
    Base model for permission fields.

    Attributes:
        name (str): Unique permission identifier (e.g., "user:read", "article:delete").
        description (str): Human-readable description of what this permission allows.
        resource_type (str): Type of resource this permission applies to (e.g., "user", "article").
        action (str): Action this permission allows (e.g., "read", "write", "delete", "manage").
    """

    name: str = Field(unique=True, index=True, max_length=255)
    description: str = Field(default="", max_length=500)
    resource_type: str = Field(index=True, max_length=100)
    action: str = Field(index=True, max_length=100)


class Permission(PermissionBase, table=True):
    """
    Database model representing a permission.

    Permissions are atomic actions that can be performed on resources.
    They are combined into roles, which are then assigned to users.

    Attributes:
        id (uuid.UUID): Unique permission identifier.
    """

    __tablename__ = "permission"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class PermissionCreate(SQLModel):
    """
    Schema for creating a new permission.

    Attributes:
        name (str): Unique permission identifier.
        description (str): Human-readable description.
        resource_type (str): Type of resource.
        action (str): Action allowed.
    """

    name: str = Field(max_length=255)
    description: str = Field(default="", max_length=500)
    resource_type: str = Field(max_length=100)
    action: str = Field(max_length=100)


class PermissionUpdate(SQLModel):
    """
    Schema for updating a permission.

    Attributes:
        description (Optional[str]): Updated description.
    """

    description: Optional[str] = Field(default=None, max_length=500)


class PermissionPublic(PermissionBase):
    """
    Public schema for exposing permission data.

    Attributes:
        id (uuid.UUID): Unique permission identifier.
    """

    id: uuid.UUID

    class Config:
        from_attributes = True
