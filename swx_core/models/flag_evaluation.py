# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FlagEvaluationBase(Base):
    flag_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_feature_flag.id"), nullable=False, index=True))
    user_id: uuid.UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_users.id"), nullable=True))
    variant: str | None = Field(default=None, max_length=100)
    value: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    reason: str = Field(default="default", max_length=50)
    context: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))


class FlagEvaluation(FlagEvaluationBase, table=True):
    __tablename__ = "swx_flag_evaluation"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))


class FlagEvaluationCreate(SQLModel):
    flag_id: uuid.UUID
    user_id: uuid.UUID | None = None
    variant: str | None = None
    value: dict[str, Any] | None = None
    reason: str = Field(default="default", max_length=50)
    context: dict[str, Any] | None = None


class FlagEvaluationPublic(SQLModel):
    id: uuid.UUID
    flag_id: uuid.UUID
    user_id: uuid.UUID | None = None
    variant: str | None = None
    value: dict[str, Any] | None = None
    reason: str
    context: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}