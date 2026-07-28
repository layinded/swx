# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SSOSessionBase(Base):
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    provider_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_sso_provider.id"), nullable=False, index=True))
    idp_session_id: str | None = Field(default=None, max_length=500)
    idp_user_id: str | None = Field(default=None, max_length=500)
    idp_attributes: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    status: str = Field(default="active", sa_column=Column(String(20), nullable=False, index=True))
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSONB, nullable=True))


class SSOSession(SSOSessionBase, table=True):
    __tablename__ = "swx_sso_session"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now()))


class SSOSessionCreate(SQLModel):
    user_id: uuid.UUID
    provider_id: uuid.UUID
    idp_session_id: str | None = Field(default=None, max_length=500)
    idp_user_id: str | None = Field(default=None, max_length=500)
    idp_attributes: dict[str, Any] | None = None
    status: str = Field(default="active", max_length=20)
    expires_at: datetime | None = None
    metadata_: dict[str, Any] | None = None


class SSOSessionUpdate(SQLModel):
    idp_session_id: str | None = Field(default=None, max_length=500)
    idp_user_id: str | None = Field(default=None, max_length=500)
    idp_attributes: dict[str, Any] | None = None
    status: str | None = Field(default=None, max_length=20)
    expires_at: datetime | None = None
    metadata_: dict[str, Any] | None = None


class SSOSessionPublic(SSOSessionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
