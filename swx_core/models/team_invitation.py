"""
Team Invitation Model
---------------------
This module defines the TeamInvitation model for team invitation management.

Team invitations allow users to be invited to teams via email, with
expiration, acceptance, and audit trail.
"""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel
from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class InvitationStatus(str, Enum):
    """Status of a team invitation."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class TeamInvitationBase(Base):
    """
    Base model for team invitation fields.

    Attributes:
        team_id (uuid.UUID): The team being invited to.
        inviter_id (uuid.UUID): The user who sent the invitation.
        invitee_email (str): Email address of the invitee.
        team_role_id (uuid.UUID): The role to assign upon acceptance.
        message (Optional[str]): Optional message from the inviter.
        expires_at (datetime): When the invitation expires.
    """
    team_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_team.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    inviter_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_users.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        )
    )
    invitee_email: str = Field(max_length=255, index=True)
    team_role_id: uuid.UUID = Field(
        sa_column=Column(
            PG_UUID(as_uuid=True),
            ForeignKey("swx_team_role.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    message: Optional[str] = Field(default=None, max_length=500)
    expires_at: datetime = Field(
        default_factory=lambda: utc_now() + timedelta(days=7),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TeamInvitation(TeamInvitationBase, table=True):
    """
    Database model representing a team invitation.

    Team invitations enable users to invite others to join a team
    via email, with expiration and audit trail.

    Attributes:
        id (uuid.UUID): Unique identifier for the invitation.
        status (InvitationStatus): Current status of the invitation.
        token (str): Secure token for accepting the invitation.
        accepted_at (Optional[datetime]): When the invitation was accepted.
        rejected_at (Optional[datetime]): When the invitation was rejected.
        created_at (datetime): When the invitation was created.
        updated_at (datetime): When the invitation was last updated.
    """
    __tablename__ = "swx_team_invitation"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    status: InvitationStatus = Field(default=InvitationStatus.PENDING)
    token: str = Field(unique=True, index=True, max_length=64)
    accepted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    rejected_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )


class TeamInvitationCreate(SQLModel):
    """
    Schema for creating a team invitation.

    Attributes:
        team_id (uuid.UUID): The team to invite to.
        invitee_email (str): Email address of the invitee.
        team_role_id (uuid.UUID): The role to assign upon acceptance.
        message (Optional[str]): Optional message from the inviter.
    """
    team_id: uuid.UUID
    invitee_email: str = Field(max_length=255)
    team_role_id: uuid.UUID
    message: Optional[str] = Field(default=None, max_length=500)


class TeamInvitationPublic(TeamInvitationBase):
    """
    Public schema for team invitation data.

    Attributes:
        id (uuid.UUID): Unique identifier.
        status (InvitationStatus): Current status.
        created_at (datetime): When created.
        expires_at (datetime): When expires.
    """
    id: uuid.UUID
    status: InvitationStatus
    created_at: datetime
    class Config:
        from_attributes = True
