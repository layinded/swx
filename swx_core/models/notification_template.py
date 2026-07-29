# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Text, func
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class NotificationTemplateBase(Base):
    key: str = Field(index=True, unique=True, max_length=100)
    channel: str = Field(index=True, max_length=20)
    subject_template: str | None = Field(default=None, max_length=500)
    body_template: str = Field(sa_column=Column(Text, nullable=False))
    is_active: bool = True

class NotificationTemplate(NotificationTemplateBase, table=True):
    __tablename__ = "swx_notification_template"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class NotificationTemplateCreate(SQLModel):
    key: str = Field(max_length=100)
    channel: str = Field(max_length=20)
    subject_template: str | None = Field(default=None, max_length=500)
    body_template: str
    is_active: bool = True

class NotificationTemplatePublic(NotificationTemplateBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True
