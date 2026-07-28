# pyright: reportUnannotatedClassAttribute=false, reportExplicitAny=false

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.config.settings import SAFETY_MAX_CONTENT_LENGTH
from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SafetyCheckBase(Base):
    content_type: str = Field(max_length=50)
    content_hash: str = Field(max_length=64)
    content_preview: str | None = Field(default=None, sa_column=Column(String(200), nullable=True))
    source: str = Field(max_length=100)
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))
    conversation_id: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_conversation.id"), nullable=True, index=True))
    filter_results: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    overall_verdict: str = Field(default="safe", max_length=20)
    action_taken: str = Field(default="none", max_length=20)
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSONB, nullable=True))


class SafetyCheck(SafetyCheckBase, table=True):
    __tablename__ = "swx_safety_check"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))


class SafetyCheckCreate(SQLModel):
    content_type: str = Field(max_length=50)
    content_hash: str = Field(max_length=64)
    content_preview: str | None = None
    source: str = Field(max_length=100)
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    filter_results: dict[str, Any] | None = None
    overall_verdict: str = "safe"
    action_taken: str = "none"
    metadata_: dict[str, Any] | None = None


class SafetyCheckUpdate(SQLModel):
    filter_results: dict[str, Any] | None = None
    overall_verdict: str | None = None
    action_taken: str | None = None
    metadata_: dict[str, Any] | None = None


class SafetyCheckPublic(SQLModel):
    id: uuid.UUID
    content_type: str
    content_hash: str
    content_preview: str | None = None
    source: str
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    filter_results: dict[str, Any] | None = None
    overall_verdict: str
    action_taken: str
    metadata_: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SafetyCheckRequest(SQLModel):
    content: str = Field(max_length=SAFETY_MAX_CONTENT_LENGTH)
    content_type: str = Field(default="input", max_length=50)
    source: str = Field(default="direct", max_length=100)
    conversation_id: uuid.UUID | None = None
