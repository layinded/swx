import uuid
from datetime import datetime, timedelta

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.models.team_invitation import InvitationStatus
from swx_core.utils.time import utc_now

class OrganizationInvitationBase(Base):
    organization_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_organization.id", ondelete="CASCADE"), index=True, nullable=False))
    inviter_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id", ondelete="CASCADE"), index=True, nullable=False))
    invitee_email: str = Field(max_length=255, index=True)
    role: str = Field(default="member", max_length=20)
    message: str | None = Field(default=None, max_length=500)
    expires_at: datetime = Field(default_factory=lambda: utc_now() + timedelta(days=7))

class OrganizationInvitation(OrganizationInvitationBase, table=True):
    __tablename__ = "swx_organization_invitation"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    status: str = Field(default=InvitationStatus.PENDING.value, max_length=20)
    token: str = Field(unique=True, index=True, max_length=64)
    accepted_at: datetime | None = Field(default=None)
    rejected_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now, sa_column_kwargs={"onupdate": utc_now})

class OrganizationInvitationCreate(SQLModel):
    organization_id: uuid.UUID
    invitee_email: str = Field(max_length=255)
    role: str = Field(default="member", max_length=20)
    message: str | None = Field(default=None, max_length=500)

class OrganizationInvitationPublic(OrganizationInvitationBase):
    id: uuid.UUID
    status: str
    token: str
    created_at: datetime

    class Config:
        from_attributes = True
