# pyright: reportUnannotatedClassAttribute=false

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _prefix(raw_key: str) -> str:
    return raw_key[:8]


class ApiKeyBase(Base):
    name: str = Field(max_length=100)
    key_prefix: str = Field(max_length=8, index=True)
    hashed_key: str = Field(max_length=64, unique=True, index=True)
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))
    expires_at: Optional[datetime] = Field(default=None)
    last_used_at: Optional[datetime] = Field(default=None)
    rate_limit_override: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    metadata_: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSONB, server_default="'{}'::jsonb", nullable=False))


class ApiKey(ApiKeyBase, table=True):
    __tablename__ = "swx_api_key"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))


class ApiKeyScopeBase(Base):
    api_key_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_api_key.id"), nullable=False, index=True))
    resource: str = Field(max_length=50, index=True)
    action: str = Field(max_length=50, index=True)
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))


class ApiKeyScope(ApiKeyScopeBase, table=True):
    __tablename__ = "swx_api_key_scope"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))


class ApiKeyCreate(SQLModel):
    name: str = Field(max_length=100)
    scopes: list[dict[str, str]] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    rate_limit_override: Optional[int] = None


class ApiKeyScopeCreate(SQLModel):
    resource: str = Field(max_length=50)
    action: str = Field(max_length=50)


class ApiKeyPublic(SQLModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    user_id: uuid.UUID
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    rate_limit_override: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes: bool = True


class ApiKeyScopePublic(SQLModel):
    id: uuid.UUID
    api_key_id: uuid.UUID
    resource: str
    action: str
    is_active: bool

    model_config = {"from_attributes": True}


class ApiKeyPublicWithScopes(ApiKeyPublic):
    scopes: list[ApiKeyScopePublic] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(SQLModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    raw_key: str
    scopes: list[ApiKeyScopePublic]
    expires_at: Optional[datetime]
    created_at: datetime
