# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class WebhookEndpointBase(Base):
    name: str = Field(max_length=100)
    url: str = Field(max_length=2000)
    secret: str = Field(max_length=500)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true")))
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    event_types: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")))
    headers: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    retry_count: int = Field(default=3, sa_column=Column(Integer, nullable=False, server_default="3"))
    retry_delay_seconds: int = Field(default=60, sa_column=Column(Integer, nullable=False, server_default="60"))
    timeout_seconds: int = Field(default=30, sa_column=Column(Integer, nullable=False, server_default="30"))

class WebhookEndpoint(WebhookEndpointBase, table=True):
    __tablename__ = "swx_webhook_endpoint"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class WebhookEndpointCreate(SQLModel):
    name: str = Field(max_length=100)
    url: str = Field(max_length=2000)
    secret: str = Field(max_length=500)
    description: str | None = None
    event_types: list[str] = Field(default_factory=list)
    headers: dict[str, Any] | None = None
    retry_count: int | None = None
    retry_delay_seconds: int | None = None
    timeout_seconds: int | None = None

class WebhookEndpointUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=100)
    url: str | None = Field(default=None, max_length=2000)
    secret: str | None = Field(default=None, max_length=500)
    description: str | None = None
    headers: dict[str, Any] | None = None
    retry_count: int | None = None
    retry_delay_seconds: int | None = None
    timeout_seconds: int | None = None
    is_active: bool | None = None

class WebhookEndpointPublic(SQLModel):
    id: uuid.UUID
    name: str
    url: str
    description: str | None = None
    is_active: bool
    user_id: uuid.UUID
    event_types: list[str] = Field(default_factory=list)
    headers: dict[str, Any] | None = None
    retry_count: int
    retry_delay_seconds: int
    timeout_seconds: int
    secret_masked: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
