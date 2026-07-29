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
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class TeamBase(Base):
    """
    Base model for team fields.

    Attributes:
        name (str): Team name.
        description (Optional[str]): Team description.
        tenant_id (Optional[uuid.UUID]): For multi-tenant support, the tenant this team belongs to.
        owner_id (Optional[uuid.UUID]): Team owner user ID.
    """

    name: str = Field(index=True, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    tenant_id: Optional[uuid.UUID] = Field(default=None, index=True)
    owner_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_users.id", ondelete="SET NULL"),
            index=True,
            nullable=True,
        )
    )


class Team(TeamBase, table=True):
    """
    Database model representing a team.

    Teams allow grouping users and scoping roles and permissions.
    This enables multi-tenant applications and team-based access control.

    Attributes:
        id (uuid.UUID): Unique team identifier.
    """

    __tablename__ = "swx_team"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )


class TeamCreate(SQLModel):
    """
    Schema for creating a new team.

    Attributes:
        name (str): Team name.
        description (Optional[str]): Team description.
        tenant_id (Optional[uuid.UUID]): Optional tenant ID for multi-tenant support.
        owner_id (Optional[uuid.UUID]): Optional owner user ID.
    """

    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    tenant_id: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None


class TeamUpdate(SQLModel):
    """
    Schema for updating a team.

    Attributes:
        name (Optional[str]): Updated team name.
        description (Optional[str]): Updated team description.
        owner_id (Optional[uuid.UUID]): Updated owner user ID.
    """

    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    owner_id: Optional[uuid.UUID] = None


class TeamPublic(TeamBase):
    """
    Public schema for exposing team data.

    Attributes:
        id (uuid.UUID): Unique team identifier.
        created_at (datetime): Team creation timestamp.
        updated_at (datetime): Team last update timestamp.
    """

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
