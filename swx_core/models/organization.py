import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OrganizationRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    API_ONLY = "api_only"


class OrganizationBase(Base):
    name: str = Field(index=True, max_length=255)
    slug: str = Field(unique=True, index=True, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    owner_id: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id", ondelete="SET NULL"), index=True, nullable=True))
    is_active: bool = True
    is_verified: bool = False
    settings: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, default=dict))


class Organization(OrganizationBase, table=True):
    __tablename__ = "swx_organization"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive)
    updated_at: datetime = Field(default_factory=utc_now_naive, sa_column_kwargs={"onupdate": utc_now_naive})


class OrganizationMemberBase(Base):
    organization_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_organization.id", ondelete="CASCADE"), index=True, nullable=False))
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id", ondelete="CASCADE"), index=True, nullable=False))
    role: str = Field(default=OrganizationRole.MEMBER.value, max_length=20)
    is_active: bool = True
    invited_by: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=True))
    joined_at: datetime = Field(default_factory=utc_now_naive)


class OrganizationMember(OrganizationMemberBase, table=True):
    __tablename__ = "swx_organization_member"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member_user_org"), {"extend_existing": True})
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive)
    updated_at: datetime = Field(default_factory=utc_now_naive, sa_column_kwargs={"onupdate": utc_now_naive})


class OrganizationCreate(SQLModel):
    name: str = Field(max_length=255)
    slug: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    owner_id: uuid.UUID | None = None
    is_active: bool = True
    is_verified: bool = False
    settings: dict[str, object] = Field(default_factory=dict)


class OrganizationUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    slug: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    owner_id: uuid.UUID | None = None
    is_active: bool | None = None
    is_verified: bool | None = None
    settings: dict[str, object] | None = None


class OrganizationPublic(OrganizationBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrganizationMemberCreate(SQLModel):
    organization_id: uuid.UUID
    user_id: uuid.UUID
    role: str = Field(default=OrganizationRole.MEMBER.value, max_length=20)
    invited_by: uuid.UUID | None = None
    is_active: bool = True


class OrganizationMemberUpdate(SQLModel):
    role: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class OrganizationMemberPublic(OrganizationMemberBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
