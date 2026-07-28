# pyright: reportUnannotatedClassAttribute=false, reportExplicitAny=false

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ContentFilterBase(Base):
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    filter_type: str = Field(max_length=50)
    config: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    severity: str = Field(default="medium", max_length=20)
    action: str = Field(default="flag", max_length=20)
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))
    category: str | None = Field(default=None, sa_column=Column(String(100), nullable=True))


class ContentFilter(ContentFilterBase, table=True):
    __tablename__ = "swx_content_filter"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now()))


class ContentFilterCreate(SQLModel):
    name: str = Field(max_length=200)
    description: str | None = None
    filter_type: str = Field(max_length=50)
    config: dict[str, Any] | None = None
    severity: str = "medium"
    action: str = "flag"
    enabled: bool = True
    category: str | None = None


class ContentFilterUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    filter_type: str | None = None
    config: dict[str, Any] | None = None
    severity: str | None = None
    action: str | None = None
    enabled: bool | None = None
    category: str | None = None


class ContentFilterPublic(SQLModel):
    id: uuid.UUID
    name: str
    description: str | None
    filter_type: str
    config: dict[str, Any] | None = None
    severity: str
    action: str
    enabled: bool
    category: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
