# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class NotificationBase(Base):
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    channel: str = Field(index=True, max_length=20)
    notification_type: str = Field(index=True, max_length=50)
    subject: str | None = Field(default=None, max_length=500)
    body: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(default="pending", index=True, max_length=20)
    provider_config_id: uuid.UUID | None = None
    provider_name: str | None = Field(default=None, max_length=50)
    provider_response: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None

class Notification(NotificationBase, table=True):
    __tablename__ = "swx_notification"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider_response: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class NotificationCreate(SQLModel):
    user_id: uuid.UUID
    channel: str = Field(max_length=20)
    notification_type: str = Field(max_length=50)
    subject: str | None = Field(default=None, max_length=500)
    body: str
    status: str = Field(default="pending", max_length=20)
    provider_config_id: uuid.UUID | None = None
    provider_name: str | None = Field(default=None, max_length=50)
    provider_response: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None

class NotificationPublic(NotificationBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True
