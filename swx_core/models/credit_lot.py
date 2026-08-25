# pyright: reportUnannotatedClassAttribute=false

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel

from swx_core.models.base import Base
from swx_core.utils.time import utc_now


class CreditLot(Base, table=True):
    """Per-credit tracking for token expiry. FIFO consumption (bonus first)."""

    __tablename__ = "swx_credit_lot"
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    source: str = Field(sa_column=Column(String(20), nullable=False))
    tokens_total: int = Field(sa_column=Column(Integer, nullable=False))
    tokens_consumed: int = Field(default=0, sa_column=Column(Integer, nullable=False, server_default="0"))
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    reference: str = Field(sa_column=Column(String(255), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()))


class CreditLotPublic(SQLModel):
    id: uuid.UUID
    account_id: uuid.UUID
    source: str
    tokens_total: int
    tokens_consumed: int
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes: bool = True