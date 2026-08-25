# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Index, String, func
from sqlmodel import Field

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class InboundWebhookDelivery(Base, table=True):
    """Tracks inbound payment-provider webhook deliveries for idempotency.

    Distinct from ``WebhookDelivery`` (which tracks outbound deliveries TO
    endpoints). This model records which inbound webhooks have already been
    processed so duplicate provider deliveries don't cause double credits.
    """

    __tablename__ = "swx_inbound_webhook_delivery"
    __table_args__ = (
        Index("idx_swx_inbound_webhook_provider_event", "provider", "event_id"),
        Index("idx_swx_inbound_webhook_created", "created_at"),
        {"extend_existing": True},
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    provider: str = Field(sa_column=Column(String(20), nullable=False, index=True))
    event_id: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    reference: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    payload_hash: str = Field(sa_column=Column(String(64), nullable=False))
    processed_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )