# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class FeatureFlagBase(Base):
    key: str = Field(max_length=200, unique=True, index=True)
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    enabled: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    default_value: dict[str, Any] | None = Field(default=None, sa_column=Column("default_value", JSONB, nullable=True))
    rules: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    variants: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    sticky: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    start_date: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    end_date: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSONB, nullable=True))

class FeatureFlag(FeatureFlagBase, table=True):
    __tablename__ = "swx_feature_flag"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class FeatureFlagCreate(SQLModel):
    key: str = Field(max_length=200)
    name: str = Field(max_length=200)
    description: str | None = None
    enabled: bool = False
    default_value: dict[str, Any] | None = None
    rules: dict[str, Any] | None = None
    variants: dict[str, Any] | None = None
    sticky: bool = False
    start_date: datetime | None = None
    end_date: datetime | None = None
    metadata_: dict[str, Any] | None = None

class FeatureFlagUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    default_value: dict[str, Any] | None = None
    rules: dict[str, Any] | None = None
    variants: dict[str, Any] | None = None
    sticky: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    metadata_: dict[str, Any] | None = None

class FeatureFlagPublic(SQLModel):
    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    enabled: bool
    default_value: dict[str, Any] | None = None
    rules: dict[str, Any] | None = None
    variants: dict[str, Any] | None = None
    sticky: bool
    start_date: datetime | None = None
    end_date: datetime | None = None
    metadata_: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}