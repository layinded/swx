# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Integer, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class SMSProviderConfigBase(Base):
    name: str = Field(index=True, unique=True, max_length=50)
    provider_type: str = Field(index=True, max_length=30)
    account_sid: str | None = Field(default=None, max_length=255)
    auth_token: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    username: str | None = Field(default=None, max_length=255)
    from_number: str | None = Field(default=None, max_length=20)
    is_active: bool = True
    priority: int = 0
    max_retries: int = 3
    timeout_seconds: int = 30
    extra_config: dict[str, Any] = Field(default_factory=dict)

class SMSProviderConfig(SMSProviderConfigBase, table=True):
    __tablename__ = "swx_sms_provider_config"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    priority: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    max_retries: int = Field(default=3, sa_column=Column(Integer, nullable=False, server_default="3"))
    timeout_seconds: int = Field(default=30, sa_column=Column(Integer, nullable=False, server_default="30"))
    extra_config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class SMSProviderConfigCreate(SQLModel):
    name: str = Field(max_length=50)
    provider_type: str = Field(max_length=30)
    account_sid: str | None = Field(default=None, max_length=255)
    auth_token: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    username: str | None = Field(default=None, max_length=255)
    from_number: str | None = Field(default=None, max_length=20)
    is_active: bool = True
    priority: int = 0
    max_retries: int = 3
    timeout_seconds: int = 30
    extra_config: dict[str, Any] = Field(default_factory=dict)

class SMSProviderConfigPublic(SMSProviderConfigBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True
