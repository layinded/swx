# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WebhookDeliveryBase(Base):
    endpoint_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_webhook_endpoint.id"), nullable=False, index=True))
    event_type: str = Field(max_length=255, index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    status: str = Field(default="pending", max_length=20, index=True)
    attempt_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    last_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    response_status_code: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    response_body: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class WebhookDelivery(WebhookDeliveryBase, table=True):
    __tablename__ = "swx_webhook_delivery"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))


class WebhookDeliveryCreate(SQLModel):
    endpoint_id: uuid.UUID
    event_type: str = Field(max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="pending", max_length=20)


class WebhookDeliveryPublic(SQLModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    status: str
    attempt_count: int
    last_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    response_status_code: int | None = None
    response_body: str | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
