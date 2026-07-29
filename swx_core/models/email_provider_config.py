# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class EmailProviderConfigBase(Base):
    name: str = Field(index=True, unique=True, max_length=50)
    provider_type: str = Field(index=True, max_length=30)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = None
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    from_email: str = Field(max_length=255)
    from_name: str | None = Field(default=None, max_length=100)
    is_ssl: bool = True
    is_active: bool = True
    priority: int = 0
    max_retries: int = 3
    timeout_seconds: int = 30
    cost_per_email: float | None = None
    daily_limit: int | None = None
    monthly_limit: int | None = None
    rate_limit_per_hour: int | None = None
    supported_countries: list[str] = Field(default_factory=list)
    tracking_enabled: bool = True
    open_tracking: bool = True
    click_tracking: bool = True
    reply_to: str | None = Field(default=None, max_length=255)
    extra_config: dict[str, Any] = Field(default_factory=dict)

class EmailProviderConfig(EmailProviderConfigBase, table=True):
    __tablename__ = "swx_email_provider_config"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    priority: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    max_retries: int = Field(default=3, sa_column=Column(Integer, nullable=False, server_default="3"))
    timeout_seconds: int = Field(default=30, sa_column=Column(Integer, nullable=False, server_default="30"))
    supported_countries: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")))
    extra_config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class EmailProviderConfigCreate(SQLModel):
    name: str = Field(max_length=50)
    provider_type: str = Field(max_length=30)
    host: str | None = Field(default=None, max_length=255)
    port: int | None = None
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    from_email: str = Field(max_length=255)
    from_name: str | None = Field(default=None, max_length=100)
    is_ssl: bool = True
    is_active: bool = True
    priority: int = 0
    max_retries: int = 3
    timeout_seconds: int = 30
    cost_per_email: float | None = None
    daily_limit: int | None = None
    monthly_limit: int | None = None
    rate_limit_per_hour: int | None = None
    supported_countries: list[str] = Field(default_factory=list)
    tracking_enabled: bool = True
    open_tracking: bool = True
    click_tracking: bool = True
    reply_to: str | None = Field(default=None, max_length=255)
    extra_config: dict[str, Any] = Field(default_factory=dict)

class EmailProviderConfigPublic(EmailProviderConfigBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True
