"""
Team Role Model
---------------
This module defines the TeamRole model for team-scoped roles.

Team roles are separate from system RBAC roles. They define permissions
within a team context (owner, editor, viewer) rather than system-wide
permissions (admin, member, superadmin).
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, String, Boolean, Integer, JSON
from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class TeamRoleBase(Base):
    """
    Base model for team role fields.

    Attributes:
        key (str): Unique role key (e.g., "owner", "editor", "viewer").
        name (str): Display name (e.g., "Team Owner", "Team Editor").
        description (Optional[str]): Role description.
        permissions (dict): Permission flags for team operations.
        priority (int): Higher priority = more permissions (for inheritance).
        is_system (bool): System roles cannot be deleted.
    """
    key: str = Field(unique=True, index=True, max_length=50)
    name: str = Field(max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    permissions: dict[str, bool] = Field(default_factory=dict, sa_column=Column(JSON))
    priority: int = Field(default=0)
    is_system: bool = Field(default=False)


class TeamRole(TeamRoleBase, table=True):
    """
    Database model representing a team-scoped role.

    Team roles define permissions within a team context, separate from
    system-wide RBAC roles. This allows teams to have their own role
    hierarchy (owner > editor > viewer) without polluting the global
    role namespace.

    Attributes:
        id (uuid.UUID): Unique role identifier.
        created_at (datetime): Timestamp when role was created.
        updated_at (datetime): Timestamp when role was last updated.
    """
    __tablename__ = "swx_team_role"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={"onupdate": utc_now}
    )


class TeamRoleCreate(SQLModel):
    """Schema for creating a team role."""
    key: str = Field(max_length=50)
    name: str = Field(max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    permissions: dict[str, bool] = Field(default_factory=dict)
    priority: int = Field(default=0)
    is_system: bool = Field(default=False)


class TeamRoleUpdate(SQLModel):
    """Schema for updating a team role."""
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    permissions: Optional[dict[str, bool]] = Field(default=None)
    priority: Optional[int] = Field(default=None)


class TeamRolePublic(TeamRoleBase):
    """Public schema for team role data."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Default team roles seeded on first run
DEFAULT_TEAM_ROLES = [
    {
        "key": "owner",
        "name": "Team Owner",
        "description": "Full control over team, including deletion and member management",
        "permissions": {
            "can_edit": True,
            "can_delete": True,
            "can_invite": True,
            "can_remove": True,
            "can_change_roles": True,
            "can_manage_billing": True,
        },
        "priority": 100,
        "is_system": True,
    },
    {
        "key": "editor",
        "name": "Team Editor",
        "description": "Can edit team content but cannot manage members or billing",
        "permissions": {
            "can_edit": True,
            "can_delete": False,
            "can_invite": False,
            "can_remove": False,
            "can_change_roles": False,
            "can_manage_billing": False,
        },
        "priority": 50,
        "is_system": True,
    },
    {
        "key": "viewer",
        "name": "Team Viewer",
        "description": "Read-only access to team content",
        "permissions": {
            "can_edit": False,
            "can_delete": False,
            "can_invite": False,
            "can_remove": False,
            "can_change_roles": False,
            "can_manage_billing": False,
        },
        "priority": 10,
        "is_system": True,
    },
]
