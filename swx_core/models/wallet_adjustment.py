# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class WalletAdjustmentStatus:
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class WalletAdjustmentRequest(Base, table=True):
    """Dual-control wallet adjustment — one admin proposes, another approves."""

    __tablename__ = "swx_wallet_adjustment_request"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    currency: str = Field(sa_column=Column(String(3), nullable=False))
    amount_nano: int = Field(sa_column=Column(Integer, nullable=False))
    adjustment_type: str = Field(sa_column=Column(String(10), nullable=False))
    reason: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))
    status: str = Field(default=WalletAdjustmentStatus.PROPOSED, sa_column=Column(String(20), nullable=False, server_default="'proposed'"))
    proposed_by: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_admin_user.id"), nullable=False))
    approved_by: Optional[uuid.UUID] = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), ForeignKey("swx_admin_user.id"), nullable=True))
    proposed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    approved_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    executed_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()))