# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.schema import ForeignKey
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WebhookEventSubscriptionBase(Base):
    endpoint_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_webhook_endpoint.id"), nullable=False, index=True))
    event_type: str = Field(max_length=255, index=True)
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true")))


class WebhookEventSubscription(WebhookEventSubscriptionBase, table=True):
    __tablename__ = "swx_webhook_event"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"extend_existing": True}
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now_naive, sa_column=Column(DateTime, nullable=False, server_default=func.now()))


class WebhookEventSubscriptionCreate(SQLModel):
    endpoint_id: uuid.UUID
    event_type: str = Field(max_length=255)


class WebhookEventSubscriptionPublic(SQLModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
