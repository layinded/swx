# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class SSOProviderBase(Base):
    name: str = Field(max_length=200)
    provider_type: str = Field(max_length=20)
    client_id: str | None = Field(default=None, max_length=500)
    client_secret: str | None = Field(default=None, max_length=1000)
    authorization_url: str | None = Field(default=None, max_length=1000)
    token_url: str | None = Field(default=None, max_length=1000)
    userinfo_url: str | None = Field(default=None, max_length=1000)
    issuer_url: str | None = Field(default=None, max_length=1000)
    sso_url: str | None = Field(default=None, max_length=1000)
    slo_url: str | None = Field(default=None, max_length=1000)
    certificate: str | None = Field(default=None, max_length=5000)
    scopes: list[str] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    domain: str | None = Field(default=None, sa_column=Column(String(200), nullable=True, index=True))
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSONB, nullable=True))
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true")))

class SSOProvider(SSOProviderBase, table=True):
    __tablename__ = "swx_sso_provider"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class SSOProviderCreate(SQLModel):
    name: str = Field(max_length=200)
    provider_type: str = Field(max_length=20)
    client_id: str | None = Field(default=None, max_length=500)
    client_secret: str | None = Field(default=None, max_length=1000)
    authorization_url: str | None = Field(default=None, max_length=1000)
    token_url: str | None = Field(default=None, max_length=1000)
    userinfo_url: str | None = Field(default=None, max_length=1000)
    issuer_url: str | None = Field(default=None, max_length=1000)
    sso_url: str | None = Field(default=None, max_length=1000)
    slo_url: str | None = Field(default=None, max_length=1000)
    certificate: str | None = Field(default=None, max_length=5000)
    scopes: list[str] | None = None
    domain: str | None = Field(default=None, max_length=200)
    metadata_: dict[str, Any] | None = None
    enabled: bool = True

class SSOProviderUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=200)
    provider_type: str | None = Field(default=None, max_length=20)
    client_id: str | None = Field(default=None, max_length=500)
    client_secret: str | None = Field(default=None, max_length=1000)
    authorization_url: str | None = Field(default=None, max_length=1000)
    token_url: str | None = Field(default=None, max_length=1000)
    userinfo_url: str | None = Field(default=None, max_length=1000)
    issuer_url: str | None = Field(default=None, max_length=1000)
    sso_url: str | None = Field(default=None, max_length=1000)
    slo_url: str | None = Field(default=None, max_length=1000)
    certificate: str | None = Field(default=None, max_length=5000)
    scopes: list[str] | None = None
    domain: str | None = Field(default=None, max_length=200)
    metadata_: dict[str, Any] | None = None
    enabled: bool | None = None

class SSOProviderPublic(SSOProviderBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
