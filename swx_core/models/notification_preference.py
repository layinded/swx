# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class NotificationPreferenceBase(Base):
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, unique=True, index=True))
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = False
    in_app_enabled: bool = True
    quiet_hours_start: str | None = Field(default=None, max_length=5)
    quiet_hours_end: str | None = Field(default=None, max_length=5)
    reminder_time: str | None = Field(default=None, max_length=5)
    digest_enabled: bool = False
    digest_frequency: str | None = Field(default=None, max_length=20)
    escalation_enabled: bool = False
    escalation_hours: int | None = None

class NotificationPreference(NotificationPreferenceBase, table=True):
    __tablename__ = "swx_notification_preference"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class NotificationPreferenceCreate(SQLModel):
    user_id: uuid.UUID
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = False
    in_app_enabled: bool = True
    quiet_hours_start: str | None = Field(default=None, max_length=5)
    quiet_hours_end: str | None = Field(default=None, max_length=5)
    reminder_time: str | None = Field(default=None, max_length=5)
    digest_enabled: bool = False
    digest_frequency: str | None = Field(default=None, max_length=20)
    escalation_enabled: bool = False
    escalation_hours: int | None = None

class NotificationPreferenceUpdate(SQLModel):
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    push_enabled: bool | None = None
    in_app_enabled: bool | None = None
    quiet_hours_start: str | None = Field(default=None, max_length=5)
    quiet_hours_end: str | None = Field(default=None, max_length=5)
    reminder_time: str | None = Field(default=None, max_length=5)
    digest_enabled: bool | None = None
    digest_frequency: str | None = Field(default=None, max_length=20)
    escalation_enabled: bool | None = None
    escalation_hours: int | None = None

class NotificationPreferencePublic(NotificationPreferenceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True
