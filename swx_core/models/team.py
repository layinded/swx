"""
Team Model
----------
This module defines the Team model for multi-tenant and team-based access control.

Teams allow grouping users and scoping roles and permissions to specific teams.
This enables:
- Multi-tenant applications
- Team-based collaboration
- Scoped access control
"""

import uuid
from typing import Optional
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


class TeamBase(Base):
    """
    Base model for team fields.

    Attributes:
        name (str): Team name.
        description (Optional[str]): Team description.
        tenant_id (Optional[uuid.UUID]): For multi-tenant support, the tenant this team belongs to.
    """

    name: str = Field(index=True, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    tenant_id: Optional[uuid.UUID] = Field(default=None, index=True)


class Team(TeamBase, table=True):
    """
    Database model representing a team.

    Teams allow grouping users and scoping roles and permissions.
    This enables multi-tenant applications and team-based access control.

    Attributes:
        id (uuid.UUID): Unique team identifier.
    """

    __tablename__ = "team"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class TeamCreate(SQLModel):
    """
    Schema for creating a new team.

    Attributes:
        name (str): Team name.
        description (Optional[str]): Team description.
        tenant_id (Optional[uuid.UUID]): Optional tenant ID for multi-tenant support.
    """

    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    tenant_id: Optional[uuid.UUID] = None


class TeamUpdate(SQLModel):
    """
    Schema for updating a team.

    Attributes:
        name (Optional[str]): Updated team name.
        description (Optional[str]): Updated team description.
    """

    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)


class TeamPublic(TeamBase):
    """
    Public schema for exposing team data.

    Attributes:
        id (uuid.UUID): Unique team identifier.
    """

    id: uuid.UUID

    class Config:
        from_attributes = True
