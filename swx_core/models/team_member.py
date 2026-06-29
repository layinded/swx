"""
Team Member Model
-----------------
This module defines the TeamMember model for team membership.

TeamMember represents the relationship between users and teams.
It also stores the user's role within that team.
"""

import uuid
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base


class TeamMemberBase(Base):
    """
    Base model for team member fields.

    Attributes:
        role_id (uuid.UUID): The role this user has in the team.
    """

    role_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_role.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )


class TeamMember(TeamMemberBase, table=True):
    """
    Database model representing team membership.

    TeamMember represents the relationship between users and teams,
    and stores the user's role within that team.

    Attributes:
        id (uuid.UUID): Unique identifier for this membership.
        team_id (uuid.UUID): Foreign key to the team.
        user_id (uuid.UUID): Foreign key to the user.
    """

    __tablename__ = "swx_team_member"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        {"extend_existing": True},
        # Composite unique constraint: a user cannot be in the same team twice
        # Note: SQLModel doesn't support composite unique constraints directly in __table_args__
        # This should be handled via migration or database-level constraint
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


class TeamMemberCreate(SQLModel):
    """
    Schema for creating a team membership.

    Attributes:
        team_id (uuid.UUID): The team to add the user to.
        user_id (uuid.UUID): The user to add.
        role_id (uuid.UUID): The role to assign to the user in this team.
    """

    team_id: uuid.UUID
    user_id: uuid.UUID
    role_id: uuid.UUID


class TeamMemberPublic(SQLModel):
    """
    Public schema for exposing team membership.

    Attributes:
        id (uuid.UUID): Unique identifier.
        team_id (uuid.UUID): The team.
        user_id (uuid.UUID): The user.
        role_id (uuid.UUID): The role.
    """

    id: uuid.UUID
    team_id: uuid.UUID
    user_id: uuid.UUID
    role_id: uuid.UUID

    class Config:
        from_attributes = True
