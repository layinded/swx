# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now

class ConversationBase(Base):
    title: str | None = Field(default=None, max_length=500)
    status: str = Field(default="active", max_length=20)
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSONB, nullable=True))
    user_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=False, index=True))

class Conversation(ConversationBase, table=True):
    __tablename__ = "swx_conversation"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))

class ConversationCreate(SQLModel):
    title: str | None = None
    metadata_: dict[str, Any] | None = None

class ConversationUpdate(SQLModel):
    title: str | None = None
    status: str | None = None
    metadata_: dict[str, Any] | None = None

class ConversationPublic(SQLModel):
    id: uuid.UUID
    title: str | None
    status: str
    metadata_: dict[str, Any] | None = None
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
