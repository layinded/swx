# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class DataClassification(str, Enum):
    PII = "PII"
    PHI = "PHI"
    FINANCIAL = "FINANCIAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    PUBLIC = "PUBLIC"

class ComplianceConfigBase(Base):
    key: str = Field(index=True, unique=True, max_length=100)
    value: str = Field(sa_column=Column(Text, nullable=False))
    category: str = Field(index=True, max_length=50)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))

class ComplianceConfig(ComplianceConfigBase, table=True):
    __tablename__ = "swx_compliance_config"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))

class DataSubjectRequestBase(Base):
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    request_type: str = Field(index=True, max_length=50)
    status: str = Field(default="pending", index=True, max_length=30)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    admin_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    requested_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    verification_token: str = Field(unique=True, max_length=255)
    verified: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))

class DataSubjectRequest(DataSubjectRequestBase, table=True):
    __tablename__ = "swx_data_subject_request"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))

class RetentionPolicyBase(Base):
    resource_type: str = Field(index=True, unique=True, max_length=100)
    retention_days: int = Field(sa_column=Column(Integer, nullable=False))
    action_on_expiry: str = Field(max_length=30)
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

class RetentionPolicy(RetentionPolicyBase, table=True):
    __tablename__ = "swx_retention_policy"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))

class ComplianceConfigCreate(SQLModel):
    key: str = Field(max_length=100)
    value: str
    category: str = Field(max_length=50)
    description: str | None = None
    is_active: bool = True

class ComplianceConfigPublic(ComplianceConfigBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True

class DataSubjectRequestCreate(SQLModel):
    request_type: str = Field(max_length=50)
    description: str | None = None

class DataSubjectRequestPublic(DataSubjectRequestBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True

class RetentionPolicyCreate(SQLModel):
    resource_type: str = Field(max_length=100)
    retention_days: int
    action_on_expiry: str = Field(max_length=30)
    description: str | None = None
    is_active: bool = True

class RetentionPolicyPublic(RetentionPolicyBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True
