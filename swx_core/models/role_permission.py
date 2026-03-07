"""
Role-Permission Mapping
------------------------
This module defines the many-to-many relationship between roles and permissions.

A role can have multiple permissions, and a permission can be in multiple roles.
This table maps roles to their associated permissions.
"""

import uuid
from sqlmodel import Field, SQLModel, Relationship
from swx_core.models.base import Base


class RolePermissionBase(Base):
    """
    Base model for role-permission mapping.

    This is a join table for the many-to-many relationship between
    roles and permissions.
    """

    pass


class RolePermission(RolePermissionBase, table=True):
    """
    Database model representing the many-to-many relationship between roles and permissions.

    Attributes:
        id (uuid.UUID): Unique identifier for this mapping.
        role_id (uuid.UUID): Foreign key to the role.
        permission_id (uuid.UUID): Foreign key to the permission.
    """

    __tablename__ = "role_permission"
    __table_args__ = (
        {"extend_existing": True},
        # Composite unique constraint: a role cannot have the same permission twice
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    role_id: uuid.UUID = Field(foreign_key="role.id", index=True)
    permission_id: uuid.UUID = Field(foreign_key="permission.id", index=True)


class RolePermissionCreate(SQLModel):
    """
    Schema for creating a role-permission mapping.

    Attributes:
        role_id (uuid.UUID): The role to assign the permission to.
        permission_id (uuid.UUID): The permission to assign.
    """

    role_id: uuid.UUID
    permission_id: uuid.UUID


class RolePermissionPublic(SQLModel):
    """
    Public schema for exposing role-permission mapping.

    Attributes:
        id (uuid.UUID): Unique identifier.
        role_id (uuid.UUID): The role.
        permission_id (uuid.UUID): The permission.
    """

    id: uuid.UUID
    role_id: uuid.UUID
    permission_id: uuid.UUID

    class Config:
        from_attributes = True
