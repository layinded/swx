"""
Role Model
----------
This module defines the Role model for role-based access control.

Roles are collections of permissions. Users are assigned roles, which grant them
the permissions associated with those roles.

This supports:
- System roles (built-in, cannot be deleted)
- Custom roles (user-created)
- Domain-specific roles (admin, user, system)
"""

import uuid
from typing import Optional, Literal
from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


class RoleBase(Base):
    """
    Base model for role fields.

    Attributes:
        name (str): Unique role name (e.g., "admin", "editor", "viewer").
        description (str): Human-readable description of the role.
        is_system_role (bool): Whether this is a built-in system role.
        domain (str): Domain this role belongs to ("admin", "user", "system").
    """

    name: str = Field(unique=True, index=True, max_length=255)
    description: str = Field(default="", max_length=500)
    is_system_role: bool = Field(default=False, index=True)
    # Use str with sa_column for SQLModel compatibility, Literal validation in schemas
    domain: str = Field(
        default="user",
        max_length=20,
        sa_column=Column(String(20), default="user", index=True)
    )


class Role(RoleBase, table=True):
    """
    Database model representing a role.

    Roles are collections of permissions. Users are assigned roles,
    which grant them the permissions associated with those roles.

    Attributes:
        id (uuid.UUID): Unique role identifier.
    """

    __tablename__ = "role"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class RoleCreate(SQLModel):
    """
    Schema for creating a new role.

    Attributes:
        name (str): Unique role name.
        description (str): Human-readable description.
        domain (str): Domain this role belongs to.
    """

    name: str = Field(max_length=255)
    description: str = Field(default="", max_length=500)
    domain: Literal["admin", "user", "system"] = Field(default="user")


class RoleUpdate(SQLModel):
    """
    Schema for updating a role.

    Attributes:
        description (Optional[str]): Updated description.
    """

    description: Optional[str] = Field(default=None, max_length=500)


class RolePublic(RoleBase):
    """
    Public schema for exposing role data.

    Attributes:
        id (uuid.UUID): Unique role identifier.
    """

    id: uuid.UUID

    class Config:
        from_attributes = True
