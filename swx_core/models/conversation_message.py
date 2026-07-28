# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ConversationMessageBase(Base):
    conversation_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_conversation.id"), nullable=False, index=True))
    role: str = Field(max_length=20)
    content: str = Field(sa_column=Column(Text, nullable=False))
    token_count: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    model: str | None = Field(default=None, max_length=100)
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSONB, nullable=True))
    parent_message_id: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_conversation_message.id"), nullable=True))


class ConversationMessage(ConversationMessageBase, table=True):
    __tablename__ = "swx_conversation_message"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))


class ConversationMessageCreate(SQLModel):
    role: str = Field(max_length=20)
    content: str
    token_count: int | None = None
    model: str | None = None
    metadata_: dict[str, Any] | None = None
    parent_message_id: uuid.UUID | None = None


class ConversationMessageUpdate(SQLModel):
    content: str | None = None
    metadata_: dict[str, Any] | None = None


class ConversationMessagePublic(SQLModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    token_count: int | None = None
    model: str | None = None
    metadata_: dict[str, Any] | None = None
    parent_message_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
