"""
Team Member Model
-----------------
This module defines the TeamMember model for team membership.

TeamMember represents the relationship between users and teams.
It uses team-scoped roles (TeamRole) instead of system RBAC roles.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel, Relationship
from swx_core.models.base import Base


class TeamMemberBase(Base):
    """
    Base model for team member fields.

    Attributes:
        team_role_id (uuid.UUID): The team-scoped role for this membership.
    """

    team_role_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_team_role.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )


class TeamMember(TeamMemberBase, table=True):
    """
    Database model representing team membership.

    TeamMember represents the relationship between users and teams,
    using team-scoped roles (TeamRole) for permissions within the team.

    Attributes:
        id (uuid.UUID): Unique identifier for this membership.
        team_id (uuid.UUID): Foreign key to the team.
        user_id (uuid.UUID): Foreign key to the user.
        team_role_id (uuid.UUID): Foreign key to the team-scoped role.
        created_at (datetime): When the membership was created.
        updated_at (datetime): When the membership was last updated.
    """

    __tablename__ = "swx_team_member"  # type: ignore
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_member_user_team"),
        {"extend_existing": True},
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    team_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_team.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_users.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc).replace(tzinfo=None)}
    )
    
    user: "User" = Relationship()  # type: ignore
    team_role: "TeamRole" = Relationship()  # type: ignore


class TeamMemberCreate(SQLModel):
    """
    Schema for creating a team membership.

    Attributes:
        team_id (uuid.UUID): The team to add the user to.
        user_id (uuid.UUID): The user to add.
        team_role_id (uuid.UUID): The team-scoped role to assign.
    """

    team_id: uuid.UUID
    user_id: uuid.UUID
    team_role_id: uuid.UUID


class TeamMemberUpdate(SQLModel):
    """
    Schema for updating a team membership.

    Attributes:
        team_role_id (uuid.UUID): The new team-scoped role.
    """

    team_role_id: uuid.UUID


class TeamMemberPublic(SQLModel):
    """
    Public schema for exposing team membership.

    Attributes:
        id (uuid.UUID): Unique identifier.
        team_id (uuid.UUID): The team.
        user_id (uuid.UUID): The user.
        team_role_id (uuid.UUID): The team-scoped role.
        created_at (datetime): When the membership was created.
    """

    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    team_role_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True