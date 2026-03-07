"""
User-Role Assignment
---------------------
This module defines the many-to-many relationship between users and roles.

A user can have multiple roles, and a role can be assigned to multiple users.
This table maps users to their assigned roles.

Supports:
- Global roles (apply to entire system)
- Team-scoped roles (apply to specific team)
- Resource-scoped roles (apply to specific resource)
"""

import uuid
from typing import Optional
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


class UserRoleBase(Base):
    """
    Base model for user-role assignment.

    Attributes:
        team_id (Optional[uuid.UUID]): If set, this role is scoped to a specific team.
        resource_id (Optional[uuid.UUID]): If set, this role is scoped to a specific resource.
    """

    team_id: Optional[uuid.UUID] = Field(default=None, foreign_key="team.id", index=True)
    resource_id: Optional[uuid.UUID] = Field(default=None, index=True)


class UserRole(UserRoleBase, table=True):
    """
    Database model representing the many-to-many relationship between users and roles.

    Attributes:
        id (uuid.UUID): Unique identifier for this assignment.
        user_id (uuid.UUID): Foreign key to the user.
        role_id (uuid.UUID): Foreign key to the role.
        team_id (Optional[uuid.UUID]): If set, this role is scoped to a specific team.
        resource_id (Optional[uuid.UUID]): If set, this role is scoped to a specific resource.
    """

    __tablename__ = "user_role"
    __table_args__ = (
        {"extend_existing": True},
        # Composite unique constraint: a user cannot have the same role twice in the same scope
        # Note: SQLModel doesn't support composite unique constraints directly in __table_args__
        # This should be handled via migration or database-level constraint
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    role_id: uuid.UUID = Field(foreign_key="role.id", index=True)


class UserRoleCreate(SQLModel):
    """
    Schema for creating a user-role assignment.

    Attributes:
        user_id (uuid.UUID): The user to assign the role to.
        role_id (uuid.UUID): The role to assign.
        team_id (Optional[uuid.UUID]): Optional team scope.
        resource_id (Optional[uuid.UUID]): Optional resource scope.
    """

    user_id: uuid.UUID
    role_id: uuid.UUID
    team_id: Optional[uuid.UUID] = None
    resource_id: Optional[uuid.UUID] = None


class UserRolePublic(SQLModel):
    """
    Public schema for exposing user-role assignment.

    Attributes:
        id (uuid.UUID): Unique identifier.
        user_id (uuid.UUID): The user.
        role_id (uuid.UUID): The role.
        team_id (Optional[uuid.UUID]): Optional team scope.
        resource_id (Optional[uuid.UUID]): Optional resource scope.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    role_id: uuid.UUID
    team_id: Optional[uuid.UUID] = None
    resource_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True
