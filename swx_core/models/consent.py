# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class ConsentStatus(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"

class ConsentTypeBase(Base):
    key: str = Field(index=True, unique=True, max_length=50)
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    is_required: bool = Field(default=False)
    is_active: bool = Field(default=True)

class ConsentType(ConsentTypeBase, table=True):
    __tablename__ = "swx_consent_type"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))

class UserConsentBase(Base):
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    consent_type_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_consent_type.id"), nullable=False, index=True))
    status: str = Field(default=ConsentStatus.PENDING.value, max_length=20)
    version: str = Field(max_length=20)
    granted_at: datetime | None = Field(default=None)
    withdrawn_at: datetime | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)
    ip_address: str | None = Field(default=None, max_length=50)
    user_agent: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

class UserConsent(UserConsentBase, table=True):
    __tablename__ = "swx_user_consent"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        Index("idx_swx_user_consent_user_type", "user_id", "consent_type_id"),
        Index("idx_swx_user_consent_status", "status"),
        {"extend_existing": True},
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))

class ConsentVersionBase(Base):
    consent_type_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_consent_type.id"), nullable=False, index=True))
    version: str = Field(max_length=20)
    document_url: str | None = Field(default=None, max_length=500)
    document_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    is_active: bool = Field(default=True)
    effective_date: datetime = Field(default_factory=utc_now)

class ConsentVersion(ConsentVersionBase, table=True):
    __tablename__ = "swx_consent_version"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        Index("idx_swx_consent_version_type_active", "consent_type_id", "is_active"),
        {"extend_existing": True},
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))

class ConsentTypeCreate(SQLModel):
    key: str = Field(max_length=50)
    name: str = Field(max_length=100)
    description: str | None = None
    is_required: bool = False
    is_active: bool = True

class ConsentTypePublic(ConsentTypeBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True

class UserConsentCreate(SQLModel):
    consent_type_key: str = Field(max_length=50)
    version: str = Field(max_length=20)
    source: str | None = Field(default=None, max_length=50)

class UserConsentUpdate(SQLModel):
    status: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    expires_at: datetime | None = None

class UserConsentPublic(UserConsentBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True

class ConsentVersionCreate(SQLModel):
    consent_type_id: uuid.UUID
    version: str = Field(max_length=20)
    document_url: str | None = Field(default=None, max_length=500)
    document_text: str | None = None
    is_active: bool = True
    effective_date: datetime = Field(default_factory=utc_now)

class ConsentVersionPublic(ConsentVersionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True

class ConsentSummary(SQLModel):
    user_id: uuid.UUID
    pending: int = 0
    granted: int = 0
    withdrawn: int = 0
    expired: int = 0
    total: int = 0
